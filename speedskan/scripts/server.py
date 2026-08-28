"""Webcam capture server for the scan-collectibles skill.

Serves a small page that streams webcam frames from the USER'S OWN browser
(the Claude in-app browser pane cannot access the camera) to this local server,
which writes the newest frame to ./captures/latest.jpg for Claude to Read.

Usage (run from the collection's project root so captures/ lands there):
    python .claude/skills/scan-collectibles/scripts/server.py [PORT]

Default port 8791. Frames -> ./captures/latest.jpg  (overwritten each ~2s).
The "Save snapshot" button archives a copy under ./captures/archive/.
"""
import http.server, socketserver, os, sys

BASE = os.getcwd()
CAPTURES = os.path.join(BASE, "captures")
ARCHIVE = os.path.join(CAPTURES, "archive")
LATEST = os.path.join(CAPTURES, "latest.jpg")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8791
os.makedirs(ARCHIVE, exist_ok=True)

INDEX = b"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Collectible Scanner</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin:0; background:#0e0f12; color:#e8e8ea;
    font-family: ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif;
    display:flex; flex-direction:column; align-items:center; min-height:100vh; gap:12px; padding:14px; }
  h1 { font-size:16px; font-weight:600; margin:4px 0; color:#c9c9cf; }
  #stage { position:relative; width:100%; max-width:900px; }
  video { width:100%; border-radius:14px; background:#000; display:block;
    box-shadow:0 8px 40px rgba(0,0,0,.6); transform:scaleX(-1); }
  #reticle { position:absolute; inset:8%; border:2px dashed rgba(255,255,255,.25); border-radius:12px; pointer-events:none; }
  #bar { display:flex; gap:14px; align-items:center; flex-wrap:wrap; justify-content:center; }
  button { font:inherit; font-size:14px; padding:8px 16px; border-radius:10px; border:1px solid #333;
    background:#1c1d22; color:#e8e8ea; cursor:pointer; }
  button.on { background:#12331d; border-color:#1f6d3a; color:#7ee2a0; }
  #status { font-size:13px; color:#9a9aa2; min-height:18px; text-align:center; }
  .err { color:#ff6b6b !important; }
  .dot { display:inline-block; width:9px; height:9px; border-radius:50%; background:#3a3; margin-right:6px; }
</style></head>
<body>
  <h1>&#128270; Collectible Scanner &mdash; hold an item in the box (~6-10in back to focus)</h1>
  <div id="stage"><video id="v" autoplay playsinline muted></video><div id="reticle"></div></div>
  <div id="bar">
    <button id="toggle" class="on">&#128994; Auto-scan ON</button>
    <button id="snap">&#128247; Save snapshot</button>
  </div>
  <div id="status">Requesting camera&hellip;</div>
  <canvas id="c" style="display:none"></canvas>
<script>
  const v=document.getElementById('v'), c=document.getElementById('c'), status=document.getElementById('status');
  const toggle=document.getElementById('toggle'), snap=document.getElementById('snap');
  let auto=true, sending=false, count=0;
  async function start(){
    try{
      const s=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:1280},height:{ideal:720}},audio:false});
      v.srcObject=s; status.innerHTML='<span class="dot"></span>Camera live. Auto-scan is sending frames.'; loop();
    }catch(e){ status.textContent='Camera error: '+e.name+' &mdash; '+e.message; status.className='err'; }
  }
  function grab(){ c.width=v.videoWidth; c.height=v.videoHeight;
    c.getContext('2d').drawImage(v,0,0,c.width,c.height);
    return new Promise(r=>c.toBlob(r,'image/jpeg',0.85)); }
  async function post(url){ if(sending||!v.videoWidth) return; sending=true;
    try{ const b=await grab(); await fetch(url,{method:'POST',headers:{'Content-Type':'image/jpeg'},body:b});
      count++; status.innerHTML='<span class="dot"></span>'+(url==='/snapshot'?'Saved snapshot #':'Sent frame #')+count+' at '+new Date().toLocaleTimeString();
    }catch(e){ status.textContent='Send failed: '+e.message; status.className='err'; } sending=false; }
  async function loop(){ if(auto) await post('/frame'); setTimeout(loop, 1800); }
  toggle.onclick=()=>{ auto=!auto; toggle.className=auto?'on':''; toggle.innerHTML=auto?'&#128994; Auto-scan ON':'&#9898; Auto-scan OFF'; };
  snap.onclick=()=>post('/snapshot');
  start();
</script></body></html>"""

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200); self.send_header("Content-Type","text/html"); self.end_headers()
            self.wfile.write(INDEX)
        elif self.path == "/latest.jpg" and os.path.exists(LATEST):
            data = open(LATEST, "rb").read()
            self.send_response(200); self.send_header("Content-Type","image/jpeg"); self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404); self.end_headers()
    def do_POST(self):
        if self.path in ("/frame", "/snapshot"):
            n = int(self.headers.get("Content-Length", 0)); data = self.rfile.read(n)
            with open(LATEST, "wb") as f: f.write(data)
            if self.path == "/snapshot":
                i = 1
                while os.path.exists(os.path.join(ARCHIVE, "snap-%03d.jpg" % i)): i += 1
                with open(os.path.join(ARCHIVE, "snap-%03d.jpg" % i), "wb") as f: f.write(data)
            self.send_response(204); self.end_headers()
        else:
            self.send_response(404); self.end_headers()

socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(("127.0.0.1", PORT), H) as httpd:
    print("Collectible scanner serving on http://127.0.0.1:%d  (frames -> %s)" % (PORT, LATEST), flush=True)
    httpd.serve_forever()
