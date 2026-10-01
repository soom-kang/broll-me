// Inspect rendered scene invariants and seek determinism; requires the isolated runtime.
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const {pathToFileURL} = require('url');

async function main() {
  const [input, output] = process.argv.slice(2);
  if (!input || !output) throw new Error('usage: audit_scene.js scene.html audit.json');
  const browser = await chromium.launch(process.env.BROLL_CHROMIUM ? {executablePath:process.env.BROLL_CHROMIUM} : {});
  try {
    const page = await browser.newPage({viewport:{width:640,height:360}});
    const errors = [], remote = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route(/^https?:/, route => { remote.push(route.request().url()); return route.abort(); });
    await page.addInitScript(() => {
      let engine;
      Object.defineProperty(window,'M',{configurable:true,get(){return engine;},set(value){
        engine=value; let scene;
        Object.defineProperty(value,'scene',{configurable:true,get(){return scene;},set(original){scene=function(cfg){
          window.__auditConfig={W:cfg.W,H:cfg.H,T:cfg.T,center:cfg.center,start:cfg.start,SEQ:cfg.SEQ,SH:Object.fromEntries(Object.entries(cfg.SH).map(([id,state])=>[id,Object.fromEntries(Object.entries(state).filter(([key])=>key!=='bg'))]))};
          return original(cfg);
        };}});
      }});
    });
    const url=pathToFileURL(path.resolve(input)); url.search='render';
    await page.goto(url.href); await page.evaluate(()=>document.fonts.ready);
    if (!(await page.evaluate(()=>typeof window.seek==='function'))) throw new Error('Scene did not initialize: '+JSON.stringify(errors));
    const info=await page.evaluate(()=>({W:document.querySelector('#stage').offsetWidth,H:document.querySelector('#stage').offsetHeight,T:window.DURATION,alpha:document.documentElement.classList.contains('alpha')}));
    await page.setViewportSize({width:info.W,height:info.H});
    const samples=[];
    for(const fraction of [0.1,0.5,0.85]) {
      await page.evaluate(t=>seek(t),info.T*fraction);
      samples.push(await page.evaluate(()=>Object.fromEntries(['shape','cursor','world'].map(id=>{const node=document.getElementById(id),s=getComputedStyle(node);return [id,{width:s.width,height:s.height,left:s.left,top:s.top,transform:s.transform,borderRadius:s.borderRadius}];}))));
    }
    const first=await page.screenshot({omitBackground:info.alpha});
    await page.evaluate(()=>seek(0)); await page.evaluate(t=>seek(t),info.T*0.85);
    const again=await page.screenshot({omitBackground:info.alpha});
    const fingerprint=buf=>crypto.createHash('sha256').update(buf).digest('hex');
    const report=await page.evaluate(()=>({scene:window.__auditConfig,palette:window.BROLL_PALETTE,cssRoles:window.BROLL_PALETTE ? Object.fromEntries(Object.keys(window.BROLL_PALETTE).map(role=>[role,getComputedStyle(document.documentElement).getPropertyValue('--broll-'+role.replace(/[A-Z]/g,letter=>'-'+letter.toLowerCase())).trim()])) : null,canvas:getComputedStyle(document.body).backgroundColor,koreanFontReady:Array.from(document.fonts).some(font=>font.family==='Noto Sans KR'&&font.status==='loaded'),loadedFonts:Array.from(document.fonts).filter(font=>font.status==='loaded').map(font=>font.family)}));
    Object.assign(report,{...info,geometry:samples,seekDeterministic:fingerprint(first)===fingerprint(again),frameSha256:fingerprint(first),errors,remoteRequests:remote});
    fs.mkdirSync(path.dirname(path.resolve(output)),{recursive:true});
    fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
    fs.writeFileSync(output.replace(/\.json$/,'.png'),first);
    if(errors.length || remote.length || !report.seekDeterministic) throw new Error('Scene audit failed: '+JSON.stringify({errors,remote,seekDeterministic:report.seekDeterministic}));
    console.log(JSON.stringify({input,W:info.W,H:info.H,T:info.T,alpha:info.alpha,seekDeterministic:report.seekDeterministic}));
  } finally { await browser.close(); }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
