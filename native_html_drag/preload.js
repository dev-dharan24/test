// Deliberately mirrors ScreenSnap's privileged editor shape without proprietary code.
const fs = require('fs');
const { ipcRenderer } = require('electron');
window.editorRuntime = { fs, ipcRenderer, marker: 'minimal-screen-editor-runtime' };
