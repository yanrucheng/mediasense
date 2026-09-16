// Twenty equally sized synthetic Candidates, two real tabs per Work.
const fs=require("fs"),cp=require("child_process"),assert=require("assert/strict");
const cfg=JSON.parse(fs.readFileSync(process.argv[2]));
const env={...process.env,...cfg.env};
const {chromium}=require(cfg.playwright);
const old=JSON.parse(fs.readFileSync(cfg.reference_root+"/lifecycle-trace.json"));
const candidates=JSON.parse(fs.readFileSync(cfg.reference_root+"/cli-trace.json"));
const organization=candidates.findLast(x=>x.request.organization_content?.kind==="candidate").request.organization_content;
const works=old.filter(x=>x.request.action==="create").map(x=>x.response);
assert.equal(works.length,20);
function cli(args){return JSON.parse(cp.execFileSync(cfg.host,args,{env,encoding:"utf8",timeout:90000,maxBuffer:8*1024*1024}));}
function plan(request){return cli(["tools","call","mediasense.plan.work","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify(request),"--json"]).result;}
function rss(pid){return Number(cp.execFileSync("ps",["-o","rss=","-p",String(pid)],{encoding:"utf8"}).trim());}
(async()=>{
 const browser=await chromium.launch({executablePath:cfg.browser,headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
 const context=await browser.newContext({viewport:{width:1440,height:1050}}),measurements=[],trace=[];
 try{
  for(let n=0;n<20;n++){
   const started=performance.now(),work=works[n];
   const request={action:"update",work_ref:work.work_ref,base_revision:work.revision,request_id:"request:multitab-"+n,organization_content:organization};
   const saved=plan(request);trace.push({request,response:saved});assert.equal(saved.outcome,"ok");assert.equal(saved.view.status,"ready");
   for(let tab=0;tab<2;tab++){
    const page=await context.newPage();await page.goto(saved.view.revision_uri);await page.locator("summary").waitFor();
    assert.equal(await page.locator("details.group").count(),1);assert.equal(await page.locator(".count").textContent(),"1200 个");
   }
   const status=cli(["views","status","--json"]);assert(status.contexts<=2);assert(status.active_heavy_requests<=2);
   measurements.push({work:n,tabs:context.pages().length,contexts:status.contexts,rss_kib:rss(status.pid),milliseconds:performance.now()-started});
   if(n%5===4)console.log(JSON.stringify(measurements.at(-1)));
  }
  assert.equal(context.pages().length,40);
  const last=context.pages().at(-1);await last.locator("summary").click();
  await last.waitForFunction(()=>[...document.images].some(i=>i.naturalWidth>0));
  await last.screenshot({path:cfg.root+"/forty-tabs-last-work.png"});
  fs.writeFileSync(cfg.root+"/report.json",JSON.stringify({works:20,members_per_work:1200,tabs:40,max_contexts:Math.max(...measurements.map(x=>x.contexts)),rss_kib_range:[Math.min(...measurements.map(x=>x.rss_kib)),Math.max(...measurements.map(x=>x.rss_kib))],measurements},null,2));
 }finally{
  fs.writeFileSync(cfg.root+"/trace.json",JSON.stringify(trace,null,2));await browser.close();
  fs.writeFileSync(cfg.root+"/stop.json",JSON.stringify(cli(["views","stop","--json"]),null,2));
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
