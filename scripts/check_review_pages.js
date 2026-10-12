// Verify actual viewer controls, literal metadata and responsive review layouts.
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');
const assert=require('node:assert/strict');

async function ready(page, ids){
  await page.waitForFunction(ids=>ids.every(id=>{const video=document.getElementById(id);return video.readyState>=2&&!video.seeking;})&&!document.getElementById('play').disabled,ids);
}
async function pause(page){
  await page.evaluate(()=>document.querySelectorAll('video').forEach(video=>video.pause()));
  await page.waitForFunction(()=>document.getElementById('play').textContent==='Play');
}
async function mediaError(page,source){
  await page.waitForFunction(source=>!document.getElementById('media-status').hidden&&
    document.getElementById('play').disabled&&!document.getElementById('retry').hidden&&
    document.getElementById('failed-source').textContent.split('\n').includes(source),source);
}
async function compareLoading(page){
  for(const mode of ['side','wipe-mode']){
    const ids=mode==='side'?['vA','vB']:['wBot','wTop'];
    const inactive=mode==='side'?['wBot','wTop']:['vA','vB'];
    await page.click(`[data-mode="${mode}"]`);await ready(page,ids);await pause(page);
    for(const event of ['waiting','loadstart','emptied']){
      await page.evaluate(()=>seek(1));await ready(page,ids);
      await page.click('#play');
      await page.waitForFunction(ids=>ids.every(id=>!document.getElementById(id).paused)&&document.getElementById('play').textContent==='Pause',ids);
      // An unused layout's loading events must not stop the active pair.
      await page.evaluate(({id,event})=>document.getElementById(id).dispatchEvent(new Event(event)),{id:inactive[0],event});
      assert.equal(await page.isDisabled('#play'),false);
      assert.equal(await page.evaluate(ids=>ids.every(id=>!document.getElementById(id).paused),ids),true);
      await page.evaluate(id=>document.getElementById(id).dispatchEvent(new Event('canplay')),inactive[0]);
      const id=event==='loadstart'?ids[1]:ids[0];
      await page.evaluate(({id,event})=>document.getElementById(id).dispatchEvent(new Event(event)),{id,event});
      assert.equal(await page.evaluate(ids=>ids.every(id=>document.getElementById(id).paused),ids),true,'Unavailable active pair must pause together');
      assert.equal(await page.textContent('#play'),'Play');assert.equal(await page.isDisabled('#play'),true);
      assert.equal(await page.isDisabled('#snd'),true);assert.equal(await page.getAttribute('#track','aria-disabled'),'true');
      assert.equal(await page.isVisible('#retry'),false,'Loading is not a media error');
      const frozen=await page.evaluate(ids=>ids.map(id=>document.getElementById(id).currentTime),ids);
      await page.click('h1');await page.keyboard.press('Space');
      assert.equal(await page.evaluate(ids=>ids.every(id=>document.getElementById(id).paused),ids),true);
      await page.evaluate(id=>document.getElementById(id).dispatchEvent(new Event('playing')),id);
      assert.equal(await page.isDisabled('#play'),true,'A stale playing event cannot clear the paused loading state');
      await page.evaluate(id=>document.getElementById(id).dispatchEvent(new Event('canplay')),id);await ready(page,ids);
      const recovered=await page.evaluate(ids=>ids.map(id=>({paused:document.getElementById(id).paused,time:document.getElementById(id).currentTime})),ids);
      assert.equal(recovered.every(video=>video.paused),true,'Readiness restores controls without automatic playback');
      recovered.forEach((video,index)=>assert.ok(Math.abs(video.time-frozen[index])<0.01,'Loading recovery retains the paused review time'));
      assert.ok(Math.abs(Number(await page.getAttribute('#track','aria-valuenow'))-recovered[1].time)<=0.051);
      assert.equal(await page.isVisible('#media-status'),false);
      await page.click('#play');
      await page.waitForFunction(ids=>ids.every(id=>!document.getElementById(id).paused)&&document.getElementById('play').textContent==='Pause',ids);
      await pause(page);
    }
  }
  await page.click('[data-mode="side"]');await ready(page,['vA','vB']);await pause(page);
}
async function keyboardControls(page,file){
  const viewer=file==='viewer.html', ids=viewer?['vid']:['vA','vB'];
  if(viewer)await page.click('#list button[data-i="0"]');
  else await page.click('[data-mode="side"]');
  await ready(page,ids);await pause(page);
  const muted=await page.evaluate(ids=>document.getElementById(ids.at(-1)).muted,ids);
  await page.focus('#snd');await page.keyboard.press('Space');
  assert.equal(await page.evaluate(ids=>document.getElementById(ids.at(-1)).muted,ids),!muted,'Space must activate Sound exactly once');
  assert.equal(await page.evaluate(ids=>document.getElementById(ids.at(-1)).paused,ids),true,'Sound must not toggle playback');
  if(viewer){
    await page.focus('#next');await page.keyboard.press('Space');
    assert.equal(await page.getAttribute('#list button[aria-current="true"]','data-i'),'1');
    await page.focus('#prev');await page.keyboard.press('Space');
    assert.equal(await page.getAttribute('#list button[aria-current="true"]','data-i'),'0');
    await page.focus('#list button[data-i="1"]');await page.keyboard.press('Space');
    assert.equal(await page.getAttribute('#list button[aria-current="true"]','data-i'),'1');
    await ready(page,ids);await pause(page);
    await page.focus('#auto');await page.keyboard.press('Space');
    assert.equal(await page.isChecked('#auto'),true);await page.keyboard.press('Space');
    assert.equal(await page.isChecked('#auto'),false);
  }else{
    await page.focus('[data-mode="stack"]');await page.keyboard.press('Space');
    assert.equal(await page.getAttribute('[data-mode="stack"]','aria-pressed'),'true');
    assert.equal(await page.evaluate(()=>document.getElementById('vB').paused),true);
    await page.evaluate(()=>document.querySelectorAll('video').forEach(video=>video.currentTime=1));
    await ready(page,ids);
    await page.focus('#track');await page.keyboard.press('ArrowRight');
    assert.ok(Math.abs(await page.evaluate(()=>document.getElementById('vB').currentTime)-3)<0.1,'Focused slider must seek once');
    await page.keyboard.press('Space');
    assert.equal(await page.evaluate(()=>document.getElementById('vB').paused),true,'Slider Space must not toggle playback');
    await page.focus('[data-mode="wipe-mode"]');await page.keyboard.press('Space');
    await ready(page,['wBot','wTop']);await pause(page);
    assert.equal(await page.getAttribute('[data-mode="wipe-mode"]','aria-pressed'),'true');
    await page.click('[data-mode="side"]');
  }
  await ready(page,ids);await pause(page);
  await page.click('h1');await page.keyboard.press('Space');
  await page.waitForFunction(ids=>!document.getElementById(ids.at(-1)).paused&&document.getElementById('play').textContent==='Pause',ids);
  assert.equal(await page.textContent('#play'),'Pause');
  await page.keyboard.press('Space');await pause(page);
  if(viewer){
    const before=Number(await page.getAttribute('#list button[aria-current="true"]','data-i'));
    const count=await page.locator('#list button').count();
    await page.keyboard.press('ArrowRight');
    assert.equal(Number(await page.getAttribute('#list button[aria-current="true"]','data-i')),(before+1)%count);
  }else{
    await page.evaluate(()=>document.querySelectorAll('video').forEach(video=>video.currentTime=1));
    await ready(page,ids);
    await page.keyboard.press('ArrowRight');
    assert.ok(Math.abs(await page.evaluate(()=>document.getElementById('vB').currentTime)-3)<0.1);
  }
}
async function mediaFailures(page,file,directory){
  const viewer=file==='viewer.html',active=viewer?['vid']:['vA','vB'];
  const temporary=fs.mkdtempSync(path.join(directory,'.review-media-test-'));
  try{
    for(const kind of ['missing','unsupported']){
      const target=path.join(temporary,kind+'.mp4');
      if(kind==='unsupported')fs.writeFileSync(target,'Unsupported media fixture');
      const source=pathToFileURL(target).href;
      await pause(page);
      await page.evaluate(({viewer,source})=>{
        if(viewer){const selected=document.querySelector('#list button[aria-current="true"]');CLIPS[Number(selected.dataset.i)].src=source;}
        for(const id of viewer?['vid']:['vA','wBot']){const video=document.getElementById(id);video.src=source;video.load();}
      },{viewer,source});
      await mediaError(page,source);
      assert.match(await page.textContent('#failed-source'),new RegExp(kind+'\\.mp4'));
      assert.equal(await page.textContent('#play'),'Play');
      assert.equal(await page.isDisabled('#snd'),true);assert.equal(await page.isVisible('#retry'),true);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Error reference must fit the viewport');
      if(viewer){
        assert.equal(await page.isDisabled('#next'),false);
        await page.click('#next');await ready(page,['vid']);
        assert.equal(await page.isVisible('#media-status'),false,'A healthy clip clears failure');
        await page.evaluate(source=>{const selected=document.querySelector('#list button[aria-current="true"]');CLIPS[Number(selected.dataset.i)].src=source;const video=document.getElementById('vid');video.src=source;video.load();},source);
        await mediaError(page,source);
      }else{
        assert.equal(await page.getAttribute('#track','aria-disabled'),'true');
        await page.click('[data-mode="wipe-mode"]');
        await mediaError(page,source);
        assert.match(await page.textContent('#failed-source'),new RegExp(kind+'\\.mp4'));
        await page.click('[data-mode="side"]');
      }
      if(kind==='missing')await page.screenshot({path:path.join(directory,file.replace('.html','-media-error.png')),fullPage:true});
      const good=await page.evaluate(viewer=>document.getElementById(viewer?'vid':'vB').getAttribute('src'),viewer);
      const fallback=viewer?path.join(directory,'preview.mp4'):path.resolve(directory,good);
      fs.copyFileSync(fallback,target);
      await page.click('#retry');await ready(page,active);
      assert.equal(await page.isVisible('#media-status'),false,'Restored file retry clears failure');
      assert.equal(await page.isDisabled('#snd'),false);
      await pause(page);
    }
  }finally{fs.rmSync(temporary,{recursive:true,force:true});}
}

async function main(){
  const root=path.resolve(__dirname,'..');
  const directory=path.resolve(process.argv[2]||path.join(root,'.verification'));
  const report=path.resolve(process.argv[3]||path.join(root,'reports/documentation-review-page-validation.json'));
  const browser=await chromium.launch();
  const checks=[];
  try{
    for(const width of [390,1280]){
      for(const file of ['viewer.html','compare.html']){
        const page=await browser.newPage({viewport:{width,height:844}});
        const errors=[];page.on('pageerror',error=>errors.push(error.message));
        await page.route(/^https?:/,route=>route.abort());
        await page.goto(pathToFileURL(path.join(directory,file)).href);
        await page.evaluate(()=>document.fonts.ready);
        if(file==='viewer.html'){
          await page.click('#next');
          const quote=await page.textContent('#quote');
          if(!quote.includes('Use /*FONT_CSS*/ here')||!quote.includes('<script>alert(1)</script>'))throw new Error('Literal transcript changed');
          if((await page.locator('#list button').count())<2)throw new Error('Clip list not rendered');
        }else{
          await page.evaluate(()=>seek(2));
          if(!(await page.textContent('#now')).includes('<img src=x onerror=alert(1)>'))throw new Error('Literal title changed');
          await page.click('[data-mode="wipe-mode"]');
          if(!(await page.getAttribute('#views','class')).includes('wipe-mode'))throw new Error('Compare mode does not change');
        }
        await page.evaluate(()=>document.fonts.load('500 16px "Noto Sans KR"','한글'));
        const layout=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,koreanFontReady:document.fonts.check('500 16px "Noto Sans KR"','한글')}));
        if(errors.length||layout.overflow||!layout.koreanFontReady)throw new Error(JSON.stringify({file,width,errors,layout}));
        await page.screenshot({path:path.join(directory,file.replace('.html',`-${width}.png`)),fullPage:true});
        await keyboardControls(page,file);
        if(width===390&&file==='compare.html')await compareLoading(page);
        if(width===390)await mediaFailures(page,file,directory);
        if(errors.length)throw new Error(file+' JavaScript errors: '+errors.join(';'));
        checks.push({file,width,errors,layout});await page.close();
      }
    }
    if(!process.argv[2]){
    const page=await browser.newPage({viewport:{width:1280,height:844}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.route(/^https?:/,route=>route.abort());
    await page.goto(pathToFileURL(path.join(root,'reports/improvement-review.html')).href);
    await page.click('button.view-tab:has-text("Benchmark")');
    if(!(await page.textContent('#benchmark-content')).includes('100%'))throw new Error('Benchmark scores not displayed');
    if(errors.length)throw new Error('Generated skill-creator viewer: '+errors.join(';'));
    checks.push({file:'reports/improvement-review.html',errors});
    }
    fs.writeFileSync(report,JSON.stringify({status:'passed',checks,keyboard:'native and background',media:'missing/unsupported/retry',compareLoading:'active/inactive waiting/loadstart/emptied, paused readiness recovery and manual Play'},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',checks:checks.length}));
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error.stack||error.message);process.exitCode=1;});
