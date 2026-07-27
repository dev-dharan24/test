const { app, BrowserWindow, screen } = require('electron');
const childProcess = require('child_process');
const fs = require('fs');
const http = require('http');
const path = require('path');

const kind = process.env.DROP_KIND || 'uri';
const navMode = process.env.DROP_NAV_MODE || 'default';
const helper = process.env.DROP_DRAG_HELPER;
const sourceHelper = process.env.DROP_SOURCE_HELPER;
const outDir = process.env.DROP_OUT_DIR || path.join(__dirname, 'out');
const markerPath = process.env.DROP_MARKER || path.join(outDir, `${navMode}-${kind}-marker.txt`);
const resultPath = process.env.DROP_RESULT || path.join(outDir, `${navMode}-${kind}-result.json`);
const pasteboardPath = path.join(outDir, `${navMode}-${kind}-pasteboard.json`);
const sourceReadyPath = path.join(outDir, `${navMode}-${kind}-source-ready.json`);
const sourceResultPath = path.join(outDir, `${navMode}-${kind}-source-result.json`);
const sourceLogPath = path.join(outDir, `${navMode}-${kind}-source.log`);
const screenshotPath = path.join(outDir, `${navMode}-${kind}-final.png`);

fs.mkdirSync(outDir, { recursive: true });
for (const file of [markerPath, resultPath, pasteboardPath, sourceReadyPath, sourceResultPath, sourceLogPath, screenshotPath]) {
  try { fs.unlinkSync(file); } catch (_) {}
}

const events = [];
const startedAt = Date.now();
let target;
let sourceWindow;
let sourceProcess;
let sourceReady = false;
let server;
function record(event, detail = {}) {
  const row = { time: Date.now(), ms: Date.now() - startedAt, event, ...detail };
  events.push(row);
  console.log('EVENT', JSON.stringify(row));
}
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }
function spawnLogged(command, args, logPath) {
  const fd = fs.openSync(logPath, 'a');
  const proc = childProcess.spawn(command, args, { stdio: ['ignore', fd, fd], env: process.env });
  proc.on('exit', (code, signal) => { try { fs.closeSync(fd); } catch (_) {} record('child-exit', { command, code, signal }); });
  return proc;
}
function waitExit(proc) {
  return new Promise(resolve => proc.once('exit', (code, signal) => resolve({ code, signal })));
}
async function waitForFile(file, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (fs.existsSync(file)) return true;
    await sleep(100);
  }
  return false;
}
function makePayload(label) {
  return `<!doctype html><meta charset="utf-8"><title>PAYLOAD_LOADING</title><body>${label}</body><script>
try {
  const fs = require('fs');
  const cp = require('child_process');
  const id = cp.execFileSync('/usr/bin/id', {encoding:'utf8'}).trim();
  fs.writeFileSync(${JSON.stringify(markerPath)},
    'DEFAULT_DROP_NODE_ACE=1\\nLABEL=${label}\\nID=' + id +
    '\\nNODE=' + process.versions.node + '\\nELECTRON=' + process.versions.electron +
    '\\nCHROME=' + process.versions.chrome + '\\nURL=' + location.href + '\\n');
  document.title = 'DEFAULT_DROP_NODE_ACE';
} catch (error) {
  document.title = 'PAYLOAD_ERROR:' + String(error);
}
</script>`;
}
async function stopAndSave(harnessError = null) {
  let screenshotError = null;
  try {
    const image = await target.capturePage();
    fs.writeFileSync(screenshotPath, image.toPNG());
  } catch (error) { screenshotError = String(error); }
  const markerHit = fs.existsSync(markerPath);
  const marker = markerHit ? fs.readFileSync(markerPath, 'utf8') : '';
  const finalURL = target && !target.isDestroyed() ? target.webContents.getURL() : '';
  const finalTitle = target && !target.isDestroyed() ? target.getTitle() : '';
  const result = {
    case: `${navMode}-${kind}`,
    kind,
    navMode,
    navigateOnDragDropProperty: navMode === 'enabled' ? true : (navMode === 'direct' ? 'OMITTED_DIRECT_LOAD' : 'OMITTED_DEFAULT'),
    browserWindowSecurity: { nodeIntegration: true, contextIsolation: false, webSecurity: false },
    versions: process.versions,
    markerHit,
    marker,
    initialURL: `file://${path.join(__dirname, 'target.html')}`,
    finalURL,
    finalTitle,
    harnessError,
    screenshotError,
    sourceReady,
    pasteboardCaptured: fs.existsSync(pasteboardPath),
    events
  };
  fs.writeFileSync(resultPath, JSON.stringify(result, null, 2));
  console.log('FINAL_RESULT', JSON.stringify(result));
  try { if (sourceProcess && sourceProcess.exitCode === null) sourceProcess.kill('SIGTERM'); } catch (_) {}
  try { if (sourceWindow && !sourceWindow.isDestroyed()) sourceWindow.destroy(); } catch (_) {}
  try { if (server) server.close(); } catch (_) {}
  await sleep(300);
  app.exit(harnessError ? 4 : 0);
}

app.whenReady().then(async () => {
  record('versions', { versions: process.versions, displays: screen.getAllDisplays().map(d => ({ bounds: d.bounds, scaleFactor: d.scaleFactor })) });
  if (!['link', 'uri', 'file'].includes(kind)) return stopAndSave(`bad DROP_KIND ${kind}`);
  if (!['default', 'enabled', 'direct'].includes(navMode)) return stopAndSave(`bad DROP_NAV_MODE ${navMode}`);
  if (!helper || !sourceHelper) return stopAndSave('missing helper path');

  const webPreferences = { nodeIntegration: true, contextIsolation: false, webSecurity: false };
  if (navMode === 'enabled') webPreferences.navigateOnDragDrop = true;
  target = new BrowserWindow({ x: 430, y: 30, width: 580, height: 680, show: false, title: `Drop target ${navMode}-${kind}`, webPreferences });
  for (const name of ['will-navigate', 'did-navigate', 'did-navigate-in-page']) {
    target.webContents.on(name, (_event, url, ...rest) => record(name, { url, rest }));
  }
  target.webContents.on('did-start-navigation', (_event, url, isInPlace, isMainFrame) => record('did-start-navigation', { url, isInPlace, isMainFrame }));
  target.webContents.on('did-finish-load', () => record('did-finish-load', { url: target.webContents.getURL(), title: target.getTitle() }));
  target.webContents.on('did-fail-load', (_event, code, description, url, isMainFrame) => record('did-fail-load', { code, description, url, isMainFrame }));
  target.webContents.on('will-frame-navigate', (_event, details) => record('will-frame-navigate', { details }));
  target.webContents.on('render-process-gone', (_event, details) => record('render-process-gone', details));
  target.webContents.on('console-message', (_event, level, message) => record('console-message', { level, message }));

  const remotePayload = makePayload('REMOTE_URI');
  let linkPayloadURL = '';
  server = http.createServer((request, response) => {
    record('http-request', { url: request.url, headers: request.headers });
    if ((request.url || '').startsWith('/payload')) {
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Content-Length': Buffer.byteLength(remotePayload), 'Cache-Control': 'no-store' });
      response.end(remotePayload);
    } else if ((request.url || '').startsWith('/source')) {
      const escaped = linkPayloadURL.replace(/&/g, '&amp;').replace(/\"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      const sourceHTML = `<!doctype html><meta charset="utf-8"><title>NATIVE_HYPERLINK_SOURCE</title><style>html,body{margin:0;height:100%;background:#e2e8f0;font:20px system-ui}a{position:fixed;inset:45px 30px;display:flex;align-items:center;justify-content:center;text-align:center;color:white;background:#6d28d9;border:8px solid #4c1d95;border-radius:24px;-webkit-user-drag:element}</style><a draggable="true" href="${escaped}">NATIVE CHROMIUM HYPERLINK<br>${escaped}</a>`;
      response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Content-Length': Buffer.byteLength(sourceHTML), 'Cache-Control': 'no-store' });
      response.end(sourceHTML);
    } else { response.writeHead(404); response.end('not found'); }
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const port = server.address().port;
  const localPayloadPath = path.join(outDir, `${navMode}-${kind}-local-payload.html`);
  fs.writeFileSync(localPayloadPath, makePayload('LOCAL_FILE'));
  linkPayloadURL = `http://127.0.0.1:${port}/payload?case=${navMode}-${kind}`;
  const payload = (kind === 'uri' || kind === 'link') ? linkPayloadURL : localPayloadPath;

  await target.loadFile(path.join(__dirname, 'target.html'));
  target.show();
  target.focus();
  record('target-ready', { bounds: target.getBounds(), payload, webPreferencesRequested: webPreferences });

  if (navMode === 'direct') {
    record('direct-load-start', { payload, kind });
    if (kind === 'file') await target.loadFile(localPayloadPath);
    else await target.loadURL(payload);
    const directDeadline = Date.now() + 4000;
    while (Date.now() < directDeadline && !fs.existsSync(markerPath)) await sleep(100);
    await sleep(400);
    return stopAndSave(fs.existsSync(markerPath) ? null : 'direct top-level load did not execute marker');
  }

  if (kind === 'link') {
    sourceWindow = new BrowserWindow({ x: 0, y: 30, width: 400, height: 680, show: false, title: 'Native Chromium hyperlink source', webPreferences: { nodeIntegration: false, contextIsolation: true, webSecurity: true } });
    sourceWindow.webContents.on('console-message', (_event, level, message) => record('source-console-message', { level, message }));
    await sourceWindow.loadURL(`http://127.0.0.1:${port}/source`);
    sourceWindow.show();
    sourceWindow.focus();
    sourceReady = true;
    record('chromium-hyperlink-source-ready', { bounds: sourceWindow.getBounds(), url: sourceWindow.webContents.getURL(), payload });
  } else {
    sourceProcess = spawnLogged(sourceHelper, [kind, payload, sourceReadyPath, sourceResultPath, `${navMode}-${kind}`], sourceLogPath);
    if (!(await waitForFile(sourceReadyPath, 5000))) return stopAndSave('native source did not become ready');
    sourceReady = true;
    record('source-ready', JSON.parse(fs.readFileSync(sourceReadyPath, 'utf8')));
  }
  await sleep(700);

  const dragLogPath = path.join(outDir, `${navMode}-${kind}-drag-helper.log`);
  const drag = spawnLogged(helper, ['200', '350', '720', '350', pasteboardPath], dragLogPath);
  const dragExit = await waitExit(drag);
  record('drag-helper-finished', dragExit);
  if (dragExit.code !== 0) return stopAndSave(`drag helper exit ${dragExit.code}`);

  const deadline = Date.now() + 4500;
  while (Date.now() < deadline && !fs.existsSync(markerPath)) await sleep(100);
  await sleep(500);
  await stopAndSave(null);
}).catch(error => {
  console.error('FATAL', error && error.stack || error);
  if (target) stopAndSave(String(error)); else app.exit(5);
});

app.on('window-all-closed', event => event.preventDefault());
