// Verify actual viewer controls, literal metadata and responsive review layouts.
const {chromium}=require('playwright');
const fs=require('fs');
const path=require('path');
const {pathToFileURL}=require('url');

async function main(){
  const root=path.resolve(__dirname,'..');
  const browser=await chromium.launch();
  const checks=[];
  try{
    for(const width of [390,1280]){
      for(const file of ['viewer.html','compare.html']){
        const page=await browser.newPage({viewport:{width,height:844}});
        const errors=[];page.on('pageerror',error=>errors.push(error.message));
        await page.route(/^https?:/,route=>route.abort());
        await page.goto(pathToFileURL(path.join(root,'.verification',file)).href);
        await page.evaluate(()=>document.fonts.ready);
        if(file==='viewer.html'){
          await page.click('#next');
          const quote=await page.textContent('#quote');
          if(!quote.includes('Use /*FONT_CSS*/ here')||!quote.includes('<script>alert(1)</script>'))throw new Error('Literal transcript changed');
          if((await page.locator('#list button').count())!==2)throw new Error('Clip list not rendered');
        }else{
          await page.evaluate(()=>seek(2));
          if(!(await page.textContent('#now')).includes('<img src=x onerror=alert(1)>'))throw new Error('Literal title changed');
          await page.click('[data-mode="wipe-mode"]');
          if(!(await page.getAttribute('#views','class')).includes('wipe-mode'))throw new Error('Compare mode does not change');
        }
        const layout=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,koreanFontReady:Array.from(document.fonts).some(font=>font.family==='Noto Sans KR'&&font.status==='loaded')}));
        if(errors.length||layout.overflow||!layout.koreanFontReady)throw new Error(JSON.stringify({file,width,errors,layout}));
        await page.screenshot({path:path.join(root,'.verification',file.replace('.html',`-${width}.png`)),fullPage:true});
        checks.push({file,width,errors,layout});await page.close();
      }
    }
    const page=await browser.newPage({viewport:{width:1280,height:844}});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.route(/^https?:/,route=>route.abort());
    await page.goto(pathToFileURL(path.join(root,'reports/improvement-review.html')).href);
    await page.click('button.view-tab:has-text("Benchmark")');
    if(!(await page.textContent('#benchmark-content')).includes('100%'))throw new Error('Benchmark scores not displayed');
    if(errors.length)throw new Error('Generated skill-creator viewer: '+errors.join(';'));
    checks.push({file:'reports/improvement-review.html',errors});
    fs.writeFileSync(path.join(root,'reports/documentation-review-page-validation.json'),JSON.stringify({status:'passed',checks},null,2)+'\n');
    console.log(JSON.stringify({status:'passed',checks:checks.length}));
  }finally{await browser.close();}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
