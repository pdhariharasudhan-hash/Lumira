const { app, BrowserWindow, dialog } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const path = require('path');
const fs = require('fs');
const { execFile } = require('child_process');
const configuredRoot = process.env.LUMIRA_PROJECT_ROOT;
const knownRoot = 'E:\\Hari\\personal_ai_core';
const developmentRoot = path.resolve(__dirname, '..');
const ROOT = [configuredRoot, knownRoot, developmentRoot].find(p => p && fs.existsSync(path.join(p, 'run.py')));
if (!ROOT) throw new Error('Lumira project installation was not found. Set LUMIRA_PROJECT_ROOT to the folder containing run.py.');
const PYTHON = path.join(ROOT, '.venv', 'Scripts', 'python.exe');
let backend=null, desktop=null, ownsBackend=false, ownsDesktop=false;
const singleInstance = app.requestSingleInstanceLock();
if (!singleInstance) app.quit();
app.on('second-instance', () => { const w=BrowserWindow.getAllWindows()[0]; if(w){ if(w.isMinimized())w.restore(); w.focus(); } });
function requestOk(port, route='/'){return new Promise(resolve=>{const req=http.get({host:'127.0.0.1',port,path:route,timeout:1500},res=>{res.resume();resolve(res.statusCode>=200&&res.statusCode<300)});req.on('error',()=>resolve(false));req.on('timeout',()=>{req.destroy();resolve(false)})})}
async function waitFor(port,route,timeout=30000){const end=Date.now()+timeout;while(Date.now()<end){if(await requestOk(port,route))return true;await new Promise(r=>setTimeout(r,400))}return false}
async function ensure(){
 if(!(await requestOk(8000,'/health'))){if(!fs.existsSync(PYTHON))throw Error('Lumira Python environment is missing: '+PYTHON);backend=spawn(PYTHON,['run.py'],{cwd:ROOT,windowsHide:true,env:{...process.env,HOST:'127.0.0.1',PORT:'8000',RELOAD:'false',LUMIRA_OLLAMA_CHAT_ENABLED:process.env.LUMIRA_OLLAMA_CHAT_ENABLED||'true',LUMIRA_OLLAMA_SUMMARY_ENABLED:process.env.LUMIRA_OLLAMA_SUMMARY_ENABLED||'true',LUMIRA_OLLAMA_VISION_ENABLED:process.env.LUMIRA_OLLAMA_VISION_ENABLED||'true',LUMIRA_OLLAMA_VISION_MODEL:process.env.LUMIRA_OLLAMA_VISION_MODEL||'moondream',LUMIRA_LOCAL_TRANSCRIPTION_ENABLED:process.env.LUMIRA_LOCAL_TRANSCRIPTION_ENABLED||'1',LUMIRA_LOCAL_TRANSCRIPTION_MODEL:process.env.LUMIRA_LOCAL_TRANSCRIPTION_MODEL||'base',LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE:process.env.LUMIRA_LOCAL_TRANSCRIPTION_COMPUTE_TYPE||'int8'}});ownsBackend=true;if(!(await waitFor(8000,'/health')))throw Error('Lumira backend did not start.');}
 if(!(await requestOk(5000,'/'))){const npm=process.platform==='win32'?'npm.cmd':'npm';desktop=spawn(npm,['run','dev','--','--host','127.0.0.1','--port','5000'],{cwd:path.join(ROOT,'lumira_desktop'),windowsHide:true});ownsDesktop=true;if(!(await waitFor(5000,'/')))throw Error('Lumira desktop service did not start.');}
}
async function launch(){try{await ensure();const win=new BrowserWindow({width:1440,height:900,minWidth:1000,minHeight:700,title:'Lumira',autoHideMenuBar:true,webPreferences:{contextIsolation:true,nodeIntegration:false,sandbox:true}});await win.loadURL('http://127.0.0.1:5000')}catch(e){dialog.showErrorBox('Lumira could not start',e.message||String(e));app.quit()}}
function stop(p){ if(!p||p.killed)return; if(process.platform==='win32'){ execFile('taskkill',['/pid',String(p.pid),'/t','/f'],()=>{}); } else { p.kill('SIGTERM'); } }
app.whenReady().then(launch);
app.on('window-all-closed',()=>app.quit());
app.on('before-quit',()=>{if(ownsDesktop)stop(desktop);if(ownsBackend)stop(backend)});
