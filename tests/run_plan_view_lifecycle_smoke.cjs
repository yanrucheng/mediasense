// Production timing and multi-Work acceptance. Runs only on generated Dataset.
const fs = require("fs"), cp = require("child_process"), assert = require("assert/strict");
const cfg = JSON.parse(fs.readFileSync(process.argv[2]));
const env = {...process.env, ...cfg.env};
const {chromium} = require(cfg.playwright);
const original = JSON.parse(fs.readFileSync(cfg.root + "/browser-report.json"));
const trace = [], measurements = [];
function cli(args) {
  return JSON.parse(cp.execFileSync(cfg.host, args, {env, encoding:"utf8", timeout:90000, maxBuffer:16*1024*1024}));
}
function plan(request) {
  const value = cli(["tools","call","mediasense.plan.work","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify(request),"--json"]).result;
  trace.push({request,response:value}); assert.equal(value.outcome,"ok"); return value;
}
function status() { return cli(["views","status","--json"]); }
function rss(pid) {
  try { return Number(cp.execFileSync("ps",["-o","rss=","-p",String(pid)],{encoding:"utf8"}).trim()); }
  catch { return null; }
}
function fdCount(pid) {
  try { return cp.execFileSync("lsof",["-p",String(pid),"-Fn"],{encoding:"utf8"}).split("\n").filter(l=>l.startsWith("f")).length; }
  catch { return null; }
}
function digestAuthority(normalizeOpenTime = false) {
  return cp.execFileSync(cfg.host.replace(/mediasense$/,"python"),
    [require("path").join(__dirname,"plan_view_authority_probe.py"),cfg.workspace,...(normalizeOpenTime?["--normalize-open-time"]:[])],
    {env,encoding:"utf8"});
}

(async()=>{
  // Each create gets an independent Work; no semantic edits or media preparation.
  const tokens = new Set();
  for (let n=0;n<(cfg.skip_multi_work?0:20);n++) {
    const started=performance.now();
    const work=plan({action:"create",result_ref:cfg.result_ref,request_id:"request:lifecycle-"+n});
    assert.equal(work.view.status,"ready"); tokens.add(work.view.current_uri);
    const again=plan({action:"inspect",work_ref:work.work_ref,sections:["view"]});
    assert.equal(again.sections.view.current_uri,work.view.current_uri);
    const s=status(); assert(s.contexts<=2); assert(s.active_heavy_requests<=2);
    measurements.push({work:n,contexts:s.contexts,rss_kib:rss(s.pid),fd_count:fdCount(s.pid),delivery_ms:performance.now()-started});
  }
  assert.equal(tokens.size,cfg.skip_multi_work?0:20);
  const initial=plan({action:"inspect",work_ref:original.work_ref,sections:["view"]});
  const view=initial.sections.view;
  const before=digestAuthority(), beforeBusiness=digestAuthority(true);
  fs.writeFileSync(cfg.root+"/authority-before.json",before);
  fs.writeFileSync(cfg.root+"/authority-before-normalized.json",beforeBusiness);
  const browser=await chromium.launch({executablePath:cfg.browser,headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1050}});
    let polls=0, activities=0;
    page.on("request",r=>{if(r.url().includes("/current"))polls++; if(r.url().endsWith("/activity"))activities++;});
    await page.goto(view.revision_uri);
    await page.locator("summary").first().waitFor();
    // Adapter visibility and trusted-input rules, before the no-input interval.
    const baselineActivities=activities;
    await page.evaluate(()=>{
      document.dispatchEvent(new MouseEvent("click",{bubbles:true}));
      document.dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowDown",bubbles:true}));
      document.dispatchEvent(new Event("scroll",{bubbles:true}));
    });
    await page.mouse.move(100,100);
    await page.waitForTimeout(250);
    assert.equal(activities,baselineActivities,"synthetic inputs/mouse motion renewed use");
    await page.evaluate(()=>{
      Object.defineProperty(document,"visibilityState",{value:"hidden",configurable:true});
      document.dispatchEvent(new Event("visibilitychange"));
    });
    const hiddenPolls=polls;
    await page.waitForTimeout(4500);
    assert.equal(polls,hiddenPolls,"hidden page continued polling");
    await page.evaluate(()=>{
      delete document.visibilityState;
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await page.waitForTimeout(300);
    assert(polls>hiddenPolls,"visible page did not recheck current");
    await page.locator("summary").first().click();
    await page.waitForFunction(()=>[...document.images].some(i=>i.naturalWidth>0));
    const groupCount=await page.locator("details.group").count();
    await page.screenshot({path:cfg.root+"/lifecycle-active.png"});
    let s=status(); const pid=s.pid, instance=s.instance, start=performance.now();
    assert.equal(s.limits.cache_idle,3600);assert.equal(s.limits.service_idle,259200);
    let cacheReleased=null, exited=null, lastLog=0;
    while(performance.now()-start<259280000) {
      await page.waitForTimeout(5000);
      s=status();
      const seconds=(performance.now()-start)/1000;
      measurements.push({seconds,...s,rss_kib:rss(pid)});
      if(s.state==="running" && s.contexts===0 && cacheReleased===null) {
        cacheReleased={seconds,idle_seconds:s.idle_seconds,rss_kib:rss(pid),fd_count:fdCount(pid),evictions:s.evictions};
        fs.writeFileSync(cfg.root+"/lifecycle-cache-released.json",JSON.stringify(cacheReleased,null,2));
      }
      if(seconds-lastLog>=30) { console.log(JSON.stringify({seconds,state:s.state,contexts:s.contexts,idle:s.idle_seconds,polls,activities})); lastLog=seconds; }
      if(s.state==="stopped") { exited={seconds,...s}; break; }
    }
    assert(cacheReleased,"automatic 1-hour cache release missing");
    assert(exited && exited.exit_reason==="idle_timeout","automatic 72-hour process exit missing");
    assert.equal(exited.instance,instance);assert.equal(rss(pid),null,"PID still alive after lock release");
    assert.equal(await page.locator("details.group").count(),groupCount);
    const pollsAtExit=polls;
    await page.waitForTimeout(9000);
    assert(polls-pollsAtExit<=1,"offline browser keeps polling");
    // Already-loaded content survives. Explicit new read reports connection,
    // while expanding a cached group still operates locally.
    await page.evaluate(()=>read("page",{collection:"groups"}).catch(()=>{}));
    await page.locator("#notice").filter({hasText:"继续查看时，请让 Agent 重新打开此方案。"}).waitFor();
    assert.equal(await page.locator("details.group").count(),groupCount);
    assert.equal(await page.getByText("图片无法读取",{exact:true}).count(),0);
    await page.screenshot({path:cfg.root+"/lifecycle-offline.png"});
    const afterIdle=digestAuthority();
    fs.writeFileSync(cfg.root+"/authority-after-idle.json",afterIdle);
    assert.equal(afterIdle,before,"display or lifecycle changed authority");
    const recovered=plan({action:"inspect",work_ref:original.work_ref,sections:["view"]});
    assert.equal(recovered.revision,initial.revision);
    assert.notEqual(recovered.sections.view.current_uri,view.current_uri);
    await page.goto(recovered.sections.view.revision_uri);
    await page.locator("summary").first().waitFor();
    await page.screenshot({path:cfg.root+"/lifecycle-recovered.png"});
    const afterRecovery=digestAuthority(), afterBusiness=digestAuthority(true);
    fs.writeFileSync(cfg.root+"/authority-after-recovery.json",afterRecovery);
    assert.equal(afterBusiness,beforeBusiness,"recovery changed data beyond existing Dataset-open timestamp");
    const stopped=cli(["views","stop","--json"]);assert.equal(stopped.exit_verified,true);
    fs.writeFileSync(cfg.root+"/lifecycle-report.json",JSON.stringify({production_parameters:{cache_idle:3600,service_idle:259200},synthetic_input_ignored:true,hidden_polling_paused:true,visibility_resume_checked:true,cacheReleased,exited,multi_work_bindings:tokens.size,polls,activities,authority_unchanged:true,dataset_open_timestamp_separately_recorded:true,pid_exit_verified:true,recovered_entry:recovered.sections.view,explicit_stop:stopped},null,2));
  } finally {
    fs.writeFileSync(cfg.root+"/lifecycle-measurements.json",JSON.stringify(measurements,null,2));
    fs.writeFileSync(cfg.root+"/lifecycle-trace.json",JSON.stringify(trace,null,2));
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
