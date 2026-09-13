// Interactive evaluator driver; all page/business content comes from the product.
const fs=require("fs"), path=require("path"), readline=require("readline");
const {chromium}=require("/Applications/Codex.app/Contents/Resources/cua_node/lib/node_modules/playwright-core");
const output=process.argv[2];fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
 const page=await browser.newPage({viewport:{width:1400,height:1000}});
 const events=[];page.on("pageerror",e=>events.push(e.message));
 let chain=Promise.resolve();
 async function command(c){
  if(c.op==="open"){
   if(!c.url.startsWith("http://127.0.0.1:"))throw Error("Only the delivered loopback page is allowed");
   await page.goto(c.url);
  }else if(c.op==="refresh")await page.reload();
  else if(c.op==="click")await page.getByText(c.text,{exact:true}).nth(c.index||0).click();
  else if(c.op==="image"){
   const popup=page.waitForEvent("popup");
   await page.getByRole("link",{name:c.text,exact:true}).nth(c.index||0).click();
   const picture=await popup;await picture.waitForLoadState();
   await picture.waitForFunction(()=>document.images.length>0 && document.images[0].naturalWidth>0);
   await picture.screenshot({path:path.join(output,c.capture+".png")});
   const result={image_url:picture.url(),image_size:await picture.locator("img").evaluate(i=>[i.naturalWidth,i.naturalHeight])};
   fs.appendFileSync(path.join(output,"interaction.jsonl"),JSON.stringify({command:c,result})+"\n");
   console.log(JSON.stringify(result));await picture.close();return;
  }
  else if(c.op==="stop"){await browser.close();process.exit(0);}
  if(c.wait)await page.getByText(c.wait,{exact:false}).first().waitFor();
  await page.waitForFunction(()=>!document.querySelector("#status")?.textContent.includes("正在读取"));
  if(c.op==="open"||c.op==="refresh")await page.waitForFunction(()=>Array.from(document.querySelectorAll("button")).every(b=>!b.disabled));
  if(c.capture){
   await page.evaluate(()=>document.querySelectorAll("img").forEach(i=>i.loading="eager"));
   await page.waitForFunction(()=>Array.from(document.images).every(i=>i.complete));
   await page.screenshot({path:path.join(output,c.capture+".png"),fullPage:true});
  }
  const result={url:page.url(),text:await page.locator("body").innerText(),page_errors:events.slice()};
  fs.appendFileSync(path.join(output,"interaction.jsonl"),JSON.stringify({command:c,result})+"\n");
  process.stdout.write(JSON.stringify(result)+"\n");
 }
 console.log(JSON.stringify({ready:true,browser:browser.version()}));
 for await(const line of readline.createInterface({input:process.stdin})){
  chain=chain.then(()=>command(JSON.parse(line))).catch(e=>console.log(JSON.stringify({error:e.message})));
 }
 await chain;await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});
