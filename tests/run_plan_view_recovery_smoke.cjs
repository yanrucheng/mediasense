// Real Chromium + ordinary Tool entry; delay/fault injection only at HTTP reads.
const fs = require("fs"), cp = require("child_process"), path = require("path"), assert = require("assert/strict");
const cfg = JSON.parse(fs.readFileSync(process.argv[2]));
const baseline = process.argv.includes("--baseline");
const env = {...process.env, ...cfg.env};
const {chromium} = require(cfg.playwright);
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const trace = [], results = [];
let authorityUnchanged = false;
function cli(args) {
  return JSON.parse(cp.execFileSync(cfg.host, args, {env, encoding:"utf8", timeout:90000, maxBuffer:8*1024*1024}));
}
function plan(request) {
  const response = cli(["tools","call","mediasense.plan.work","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify(request),"--json"]).result;
  trace.push({request,response});assert.equal(response.outcome,"ok");return response;
}
function authority() {
  return cp.execFileSync(cfg.host.replace(/mediasense$/, "python"), [path.join(__dirname,"plan_view_authority_probe.py"),cfg.workspace],{env,encoding:"utf8"});
}
(async()=>{
  fs.mkdirSync(cfg.root,{recursive:true});
  const created = plan({action:"create",result_ref:cfg.result_ref,request_id:"request:browser-recovery-create"});
  const saved = plan({action:"update",work_ref:created.work_ref,base_revision:created.revision,request_id:"request:browser-recovery-content",organization_content:cfg.organization});
  const view = saved.view;assert.equal(view.status,"ready");
  fs.writeFileSync(cfg.root+"/entry.json",JSON.stringify(view,null,2));
  const before = authority();
  const groupPage = await (await fetch(view.current_uri+"/page?revision="+encodeURIComponent(view.revision)+"&collection=groups")).json();
  const asset = view.current_uri+"/asset?ref="+encodeURIComponent(groupPage.items[0].samples[0].evidence_ref)+"&revision="+encodeURIComponent(view.revision);
  const browser = await chromium.launch({executablePath:cfg.browser,headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
  async function test(name, run) {
    const page = await browser.newPage({viewport:{width:1440,height:1050}}), errors=[];
    page.on("pageerror",e=>errors.push(e.message));
    const started = performance.now();
    try { await run(page);assert.deepEqual(errors,[]);results.push({name,outcome:"passed",milliseconds:performance.now()-started}); }
    catch(error) { results.push({name,outcome:"failed",message:String(error),milliseconds:performance.now()-started}); await page.screenshot({path:cfg.root+"/"+name+"-failed.png"}).catch(()=>{}); }
    finally { await page.close(); }
    console.log(JSON.stringify(results.at(-1)));
  }
  async function opened(page) { await page.goto(view.revision_uri);await page.waitForFunction(()=>document.querySelectorAll("details.group").length===50); }
  async function imageReady(page, index=0) { await page.waitForFunction(n=>{const i=document.querySelectorAll("details.group")[n]?.querySelector("img");return i?.complete&&i.naturalWidth>0;}, index, {timeout:5000}); }
  async function noOffline(page) { assert.equal(await page.getByText("继续查看时，请让 Agent 重新打开此方案。",{exact:true}).count(),0); }
  async function deadline(page, control=false) {
    await page.addInitScript(control=>{
      const original=AbortSignal.timeout.bind(AbortSignal);
      window.requestBudgets=[];
      AbortSignal.timeout=ms=>{window.requestBudgets.push(ms);return original(ms===60000||(control&&ms===10000)?1000:ms);};
      document.addEventListener("DOMContentLoaded",()=>window.initialStatus=document.querySelector('#content [role="status"]'));
    },control);
  }
  async function delay(route, milliseconds) {
    const response=await route.fetch();await pause(milliseconds);
    await route.fulfill({response}).catch(()=>{}); // The browser may already have cancelled this read.
  }
  try {
    await test("image_probe_200_recovers",async page=>{
      let native=0, probes=0;
      await page.route(asset,route=>{
        if(route.request().resourceType()==="image") {
          native++;
          if(native===1)return route.fulfill({status:503,contentType:"application/json",body:'{"error":"view_resource_busy"}'});
        } else probes++;
        return route.continue();
      });
      await opened(page);await page.locator("summary").first().click();await imageReady(page);
      assert.equal(native,2);assert.equal(probes,1);assert.equal(await page.locator(".missing").count(),0);await noOffline(page);
      await page.screenshot({path:cfg.root+"/image-recovered.png"});
    });
    await test("overview_exceeds_ten_seconds",async page=>{
      let count=0;
      await page.route("**/overview?**",route=>{count++;return delay(route,12000);});
      const started=performance.now();await page.goto(view.revision_uri);
      await pause(10500);await noOffline(page);assert.equal(await page.locator('#content [role="status"]').count(),1);
      await page.waitForFunction(()=>document.querySelectorAll("details.group").length===50,null,{timeout:6000});
      assert(performance.now()-started>12000);assert.equal(count,1);await noOffline(page);
      await page.screenshot({path:cfg.root+"/slow-overview-loaded.png"});
    });
    if (!baseline) {
      await test("image_retry_bounded_and_reexpand",async page=>{
        let native=0, probes=0, fail=true;
        await page.route(asset,route=>{
          if(route.request().resourceType()==="image") {native++;if(fail)return route.abort("failed");}
          else probes++;
          return route.continue();
        });
        await opened(page);await page.locator("summary").nth(1).click();await imageReady(page,1);
        await page.evaluate(()=>window.otherImage=document.querySelectorAll("details.group")[1].querySelector("img"));
        await page.locator("summary").first().click();await page.locator('.missing[data-temporary="true"]').waitFor();
        await pause(500);assert.equal(native,2);assert.equal(probes,1);await noOffline(page);
        fail=false;await page.locator("summary").first().click();await page.locator("summary").first().click();await imageReady(page);
        assert.equal(native,3);assert(await page.evaluate(()=>window.otherImage===document.querySelectorAll("details.group")[1].querySelector("img")));
      });
      await test("resource_failure_and_busy_remain_distinct",async page=>{
        let code="view_resource_unavailable", calls=0;
        await page.route(asset,route=>{calls++;return route.fulfill({status:503,contentType:"application/json",body:JSON.stringify({error:code})});});
        await opened(page);await page.locator("summary").first().click();await page.locator('.missing[data-temporary="false"]').waitFor();
        assert.equal(await page.getByText("图片无法读取",{exact:true}).count(),1);await noOffline(page);
        const previous=calls;await page.locator("summary").first().click();await page.locator("summary").first().click();await pause(250);assert.equal(calls,previous);
        code="view_resource_busy";await opened(page);await page.locator("summary").first().click();await page.getByText("资源繁忙，重新展开可重试。",{exact:true}).waitFor();
        await page.unroute(asset);await page.locator("summary").first().click();await page.locator("summary").first().click();await imageReady(page);
      });
      await test("initial_timeout_light_probe_and_retry",async page=>{
        await deadline(page);let reads=0, probes=0, urls=[];
        page.on("request",r=>{if(r.url().includes("/current"))probes++;});
        await page.route("**/overview?**",route=>{reads++;urls.push(route.request().url());return reads===1?delay(route,2200):route.continue();});
        await page.goto(view.current_uri);await page.getByRole("button",{name:"重试读取",exact:true}).waitFor({timeout:8000});
        await noOffline(page);assert(probes>=1);assert(await page.evaluate(()=>initialStatus===document.querySelector('#content [role="status"]')));
        assert.equal(await page.getByText("读取时间较长，请稍后重试。",{exact:true}).count(),1);
        await pause(1500);assert.equal(reads,1);await page.screenshot({path:cfg.root+"/timeout-retry.png"});
        await page.getByRole("button",{name:"重试读取",exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll("details.group").length===50);
        assert.equal(reads,2);assert.equal(new URL(urls[1]).searchParams.get("revision"),view.revision);
        assert((await page.evaluate(()=>requestBudgets)).includes(60000));await noOffline(page);
      });
      await test("pagination_timeout_preserves_content_and_cursor",async page=>{
        await deadline(page);await opened(page);await page.locator("summary").first().click();await imageReady(page);
        await page.evaluate(()=>{window.savedGroup=document.querySelector("details.group");window.savedImage=savedGroup.querySelector("img");});
        const urls=[];
        await page.route("**/page?**",route=>{
          if(!new URL(route.request().url()).searchParams.has("cursor"))return route.continue();
          urls.push(route.request().url());return urls.length===1?delay(route,2200):route.continue();
        });
        await page.getByRole("button",{name:"继续浏览",exact:true}).click();await page.getByRole("button",{name:"重试读取",exact:true}).waitFor();
        await noOffline(page);assert.equal(await page.locator("details.group").count(),50);await pause(1500);assert.equal(urls.length,1);
        await page.getByRole("button",{name:"重试读取",exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll("details.group").length===100);
        assert.equal(urls[0],urls[1]);assert(await page.evaluate(()=>savedGroup===document.querySelector("details.group")&&savedGroup.open&&savedImage===savedGroup.querySelector("img")));
      });
      await test("timeout_probe_rejects_new_revision",async page=>{
        await deadline(page);let reads=0;
        await page.route("**/overview?**",route=>{reads++;return delay(route,2200);});
        await page.route("**/current?**",route=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({revision:"work-revision:new",state:"open",idle_remaining_seconds:600})}));
        await page.goto(view.revision_uri);await page.getByText("方案已有新版本，请重新读取当前内容。",{exact:true}).waitFor();
        assert.equal(await page.locator("details.group").count(),0);assert.equal(await page.getByRole("button",{name:"重试读取",exact:true}).count(),0);assert.equal(reads,1);await noOffline(page);
      });
      await test("probe_deadline_is_not_offline",async page=>{
        await deadline(page,true);let reads=0,probes=0;
        await page.route("**/overview?**",route=>{reads++;return delay(route,3000);});
        await page.route("**/current?**",route=>{probes++;return delay(route,3000);});
        await page.goto(view.revision_uri);await page.getByRole("button",{name:"重试读取",exact:true}).waitFor({timeout:8000});
        await noOffline(page);await pause(1500);assert.equal(reads,1);assert.equal(probes,1);
        await page.unroute("**/overview?**");await page.unroute("**/current?**");
        await page.getByRole("button",{name:"重试读取",exact:true}).click();await page.waitForFunction(()=>document.querySelectorAll("details.group").length===50);await noOffline(page);
      });
      await test("confirmed_offline_stops_retries",async page=>{
        let probes=0;
        await page.route("**/overview?**",route=>route.abort("failed"));
        await page.route("**/current?**",route=>{probes++;return route.abort("failed");});
        await page.goto(view.revision_uri);await page.getByText("继续查看时，请让 Agent 重新打开此方案。",{exact:true}).waitFor();
        const count=probes;await pause(4500);assert.equal(probes,count);assert.equal(await page.locator('#content [role="status"]').count(),1);
      });
    }
    authorityUnchanged = authority() === before;
    assert(authorityUnchanged,"browser reads changed Dataset contents");
  } finally {
    await browser.close();
    fs.writeFileSync(cfg.root+"/cli-trace.json",JSON.stringify(trace,null,2));
    fs.writeFileSync(cfg.root+"/report.json",JSON.stringify({cases:results,authority_unchanged:authorityUnchanged,view},null,2));
    fs.writeFileSync(cfg.root+"/stop.json",JSON.stringify(cli(["views","stop","--json"]),null,2));
  }
  if(results.some(r=>r.outcome!=="passed"))process.exitCode=1;
})().catch(error=>{console.error(error);process.exitCode=1;});
