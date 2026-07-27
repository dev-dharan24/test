const {app, BrowserWindow, screen} = require('electron');
const path = require('path');
const fs = require('fs');
const {spawn} = require('child_process');

const mode = process.env.DRAG_SOURCE_MODE || 'electron';
const http = process.env.DRAG_SOURCE_URL || 'http://127.0.0.1:18765/source';
const helper = process.env.DRAG_HELPER;
const marker = process.env.NATIVE_DRAG_MARKER || '/tmp/native-html-drag-rce';
const result = process.env.NATIVE_DRAG_RESULT || '/tmp/native-html-drag-result.json';
const pasteboardLog = process.env.NATIVE_DRAG_PASTEBOARD_LOG || '/tmp/native-html-drag-pasteboard.json';
const sx = Number(process.env.DRAG_START_X || 260), sy = Number(process.env.DRAG_START_Y || 285);
const ex = Number(process.env.DRAG_END_X || 990), ey = Number(process.env.DRAG_END_Y || 365);
let target, source;

function save(obj) { fs.writeFileSync(result, JSON.stringify({time:Date.now(), mode, ...obj}, null, 2)); }
app.whenReady().then(async () => {
  console.log('VERSIONS', JSON.stringify(process.versions));
  console.log('DISPLAYS', JSON.stringify(screen.getAllDisplays().map(d => ({bounds:d.bounds, scaleFactor:d.scaleFactor}))));
  target = new BrowserWindow({x:650,y:30,width:680,height:680,show:false,titleBarStyle:'hiddenInset',
    transparent:true,backgroundColor:'#00000000',webPreferences:{preload:path.join(__dirname,'preload.js'),nodeIntegration:true,contextIsolation:false,webSecurity:false,webviewTag:true}});
  target.webContents.on('console-message', (_e,level,msg) => console.log('TARGET_CONSOLE',level,msg));
  target.webContents.on('will-navigate', (_e,url) => console.log('TARGET_WILL_NAVIGATE',url));
  target.webContents.on('did-navigate', (_e,url) => console.log('TARGET_DID_NAVIGATE',url));
  target.on('ready-to-show', () => { target.showInactive(); });
  await target.loadFile(path.join(__dirname,'target.html'));
  target.showInactive();
  if (mode === 'electron') {
    source = new BrowserWindow({x:20,y:30,width:570,height:680,show:false,titleBarStyle:'hiddenInset',webPreferences:{nodeIntegration:false,contextIsolation:true,webSecurity:true}});
    source.webContents.on('console-message', (_e,level,msg) => console.log('SOURCE_CONSOLE',level,msg));
    await source.loadURL(http);
    source.show(); source.focus();
  }
  if (mode === 'chrome') {
    setTimeout(() => {
      const a=spawn('/usr/bin/osascript',['-e','tell application \"Google Chrome\" to activate'],{stdio:'inherit'});
      a.on('exit', c => console.log('CHROME_ACTIVATE_EXIT',c));
    }, 1300);
  }
  console.log('BOUNDS', JSON.stringify({target:target.getBounds(), source:source && source.getBounds(), start:[sx,sy], end:[ex,ey]}));
  save({event:'windows-ready', target:target.getBounds(), source:source && source.getBounds()});
  setTimeout(() => {
    console.log('START_HELPER', helper, sx,sy,ex,ey);
    const p=spawn(helper,[String(sx),String(sy),String(ex),String(ey),pasteboardLog],{stdio:'inherit'});
    p.on('exit', code => console.log('HELPER_EXIT',code));
  }, 2500);
  const deadline=Date.now()+18000;
  const tick=setInterval(() => {
    const hit=fs.existsSync(marker);
    let drop=null,pb=null;
    try { drop=JSON.parse(fs.readFileSync(process.env.NATIVE_DRAG_DROP_LOG,'utf8')); } catch(e) {}
    try { pb=JSON.parse(fs.readFileSync(pasteboardLog,'utf8')); } catch(e) {}
    if (hit || Date.now()>deadline) {
      clearInterval(tick);
      const id=hit ? fs.readFileSync(marker,'utf8') : '';
      save({event:'finished', hit, id, url:target.webContents.getURL(), title:target.getTitle(), drop, pasteboard:pb});
      console.log('FINAL',fs.readFileSync(result,'utf8'));
      setTimeout(()=>app.exit(hit?0:3),500);
    }
  },250);
});
