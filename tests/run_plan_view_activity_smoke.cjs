const fs=require("fs"),cp=require("child_process"),assert=require("assert/strict");
const cfg=JSON.parse(fs.readFileSync(process.argv[2])),env={...process.env,...cfg.env};
const {chromium}=require(cfg.playwright);
function cli(args){return JSON.parse(cp.execFileSync(cfg.host,args,{env,encoding:"utf8",timeout:90000}));}
(async()=>{
const view=cli(["tools","call","mediasense.plan.work","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify({action:"inspect",work_ref:cfg.work_ref,sections:["view"]}),"--json"]).result.sections.view;
const browser=await chromium.launch({executablePath:cfg.browser,headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
try{
 const page=await browser.newPage();let activity=0,polls=0,assets=0;
 page.on("request",r=>{if(r.url().endsWith("/activity"))activity++;if(r.url().includes("/current"))polls++;if(r.url().includes("/asset"))assets++;});
 await page.goto(view.revision_uri);await page.locator("summary").waitFor();
 await page.evaluate(()=>{document.dispatchEvent(new MouseEvent("click",{bubbles:true}));document.dispatchEvent(new KeyboardEvent("keydown",{bubbles:true}));document.dispatchEvent(new Event("scroll"));});
 await page.mouse.move(30,30);await page.waitForTimeout(250);assert.equal(activity,0);
 await page.evaluate(()=>{Object.defineProperty(document,"visibilityState",{value:"hidden",configurable:true});document.dispatchEvent(new Event("visibilitychange"));});
 const atHide=polls;await page.waitForTimeout(4500);assert.equal(polls,atHide);
 await page.evaluate(()=>{delete document.visibilityState;document.dispatchEvent(new Event("visibilitychange"));});
 await page.waitForTimeout(350);assert(polls>atHide);assert.equal(activity,1);
 await page.keyboard.press("ArrowDown");await page.keyboard.press("ArrowUp");
 assert.equal(activity,1,"throttle allowed extra immediate notification");
 await page.waitForTimeout(30500);assert.equal(activity,2);
 assert.equal(assets,0,"cached interaction acquired media");
 fs.writeFileSync(cfg.root+"/report.json",JSON.stringify({synthetic_input_ignored:true,mouse_motion_ignored:true,hidden_polling_paused:true,visibility_resume_checked:true,trusted_keyboard_throttled:true,trailing_activity_sent:true,media_requests:assets,activities:activity},null,2));
}finally{await browser.close();fs.writeFileSync(cfg.root+"/stop.json",JSON.stringify(cli(["views","stop","--json"]),null,2));}
})().catch(e=>{console.error(e);process.exitCode=1;});
