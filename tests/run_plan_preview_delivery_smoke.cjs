// Ordinary Tool receipts and real browser controls; generated media only.
const fs = require("fs"), cp = require("child_process"), assert = require("assert/strict");
const cfg = JSON.parse(fs.readFileSync(process.argv[2]));
cfg.env = {...process.env, ...cfg.env};
const {chromium} = require(cfg.playwright);
const trace = [];
let serial = 0;
function cli(args, env = cfg.env) {
  let stdout;
  try { stdout = cp.execFileSync(cfg.host, args, {env, encoding: "utf8", timeout: 90000, maxBuffer: 8*1024*1024}); }
  catch (e) { stdout = e.stdout; if (!stdout) throw e; }
  return JSON.parse(stdout);
}
function plan(request, authority, env) {
  const args = ["tools", "call", "mediasense.plan.work", "--source", cfg.source, "--workspace", cfg.workspace, "--request", JSON.stringify(request), "--json"];
  if (authority) args.push("--authority", JSON.stringify(authority));
  const value = cli(args, env).result;
  assert(value, "No Tool result");
  trace.push({request, response: value});
  return value;
}
function update(state, fields, env) {
  const value = plan({action: "update", work_ref: state.work_ref, base_revision: state.revision, request_id: "request:browser-" + (++serial), ...fields}, null, env);
  assert.equal(value.outcome, "ok");
  return value;
}
function read(request) {
  return cli(["tools", "call", "mediasense.precheck.read", "--source", cfg.source, "--workspace", cfg.workspace, "--request", JSON.stringify(request), "--json"]).result;
}
(async () => {
  const browser = await chromium.launch({executablePath: cfg.browser, headless: true, args: ["--disable-background-networking", "--disable-component-update", "--disable-sync", "--no-first-run"]});
  const context = await browser.newContext({viewport: {width: 1440, height: 1050}});
  const page = await context.newPage();
  const jsErrors = [];
  page.on("pageerror", e => jsErrors.push(e.message));
  async function open(uri, count) {
    await page.goto(uri);
    await page.getByRole("heading", {name: "整理方案", exact: true}).waitFor();
    if (count) await page.waitForFunction(n => document.querySelectorAll("details.group").length === n, count);
    else await page.getByText("尚未保存分组。", {exact: true}).waitFor();
    assert.equal(await page.locator("details[open]").count(), 0);
  }
  async function images() {
    await page.waitForFunction(() => document.images.length > 0 && [...document.images].every(i => i.complete && i.naturalWidth > 0));
  }
  const api = async (view, collection, cursor) => {
    const u = new URL(view.current_uri + "/page");
    u.searchParams.set("revision", view.revision); u.searchParams.set("collection", collection);
    if (cursor) u.searchParams.set("cursor", cursor);
    const response = await fetch(u);
    return {status: response.status, value: await response.json()};
  };
  try {
    if (process.argv[3] === "frozen") {
      await open(process.argv[4], 1);
      await page.locator("summary").click(); await images();
      assert.equal(await page.locator("footer,aside,#binding,.evidence").count(), 0);
      await page.screenshot({path: cfg.root + "/frozen.png"});
      return;
    }
    let state = plan({action: "create", result_ref: cfg.result_ref, request_id: "request:browser-create"});
    assert.equal(state.outcome, "ok"); assert.equal(state.view.status, "ready");
    const currentEntry = state.view.current_uri;
    await open(currentEntry, 0);
    await page.screenshot({path: cfg.root + "/empty.png"});
    state = update(state, {working_notes: "先讨论方向 <script>throw new Error(123)</script>"});
    await open(currentEntry, 0);
    assert(! (await page.locator("body").innerText()).includes("先讨论方向"));
    assert((plan({action: "inspect", work_ref: state.work_ref, sections: ["working_notes"]}).sections.working_notes).includes("先讨论方向"));
    const exactPage = await context.newPage();
    const oldExact = state.view.revision_uri;
    await exactPage.goto(oldExact);
    await exactPage.getByText("尚未保存分组。", {exact: true}).waitFor();
    const scope = {kind: "precheck_relation", origin: cfg.result_ref, relation: "accounts_for", direction: "outbound"};
    const refs = read({action: "resolve", dataset_ref: cfg.dataset_ref, result_ref: cfg.result_ref, source_set: scope, page: {limit: 1000}}).members.map(x => x.source_item_ref);
    const naming = {default: "preserve_source_basename"};
    const partial = {kind: "draft", result_ref: cfg.result_ref, scope, logical_root: "合成素材整理", groups: [{relative_path: ["目录甲"], members: {kind: "explicit", source_item_refs: refs.slice(0,5)}, source_naming: naming}], other_outcomes: [], decision_notes: []};
    state = update(state, {organization_content: partial});
    await page.locator("#notice").filter({hasText: "方案已有新版本"}).waitFor();
    assert.equal(await page.locator("details.group").count(), 0);
    await page.reload(); await page.locator("details.group").waitFor(); assert.equal(page.url(), currentEntry);
    assert.deepEqual(plan({action: "inspect", work_ref: state.work_ref, sections: ["overview"]}).sections.overview.scope_summary, {scope: 1200, organized: 5, other_outcomes: 0, unassigned: 1195});
    await exactPage.reload(); await exactPage.locator("#notice").filter({hasText: "方案已有新版本"}).waitFor();
    assert.equal(exactPage.url(), oldExact); assert.equal(await exactPage.locator("details.group").count(), 0); await exactPage.close();
    await page.screenshot({path: cfg.root + "/partial.png"});
    const candidate = {...partial, kind: "candidate", groups: [{...partial.groups[0], members: scope}], decision_notes: [{summary: "图片只来自选定源素材。", applies_to: scope}]};
    state = update(state, {organization_content: candidate});
    await open(state.view.revision_uri, 1);
    assert.equal(await page.locator("img").count(), 0);
    await page.locator("summary").click(); await images();
    assert.equal(await page.locator(".gallery figure").count(), 2);
    const boxes = await page.locator("figure").evaluateAll(es => es.map(e => ({x:e.getBoundingClientRect().x,y:e.getBoundingClientRect().y})));
    assert.equal(boxes[0].y, boxes[1].y); assert(boxes[1].x > boxes[0].x);
    const revisionBeforeBrowsing = state.revision;
    const identity = plan({action: "inspect", work_ref: state.work_ref}).candidate_content_identity;
    // The removed member inspector never removes exact member continuation.
    let cursor = null, names = [], memberPages = 0;
    do { const p = await api(state.view, "group:0", cursor); assert.equal(p.status,200); names.push(...p.value.items.map(x=>x.name)); cursor=p.value.next_cursor; memberPages++; } while (cursor);
    assert.equal(names.length,1200); assert.equal(new Set(names).size,1200); assert(names.includes("item-1199.jpg")); assert.equal(memberPages,24);
    const note = await api(state.view,"note:0"); assert.equal(note.value.total,1200); assert(note.value.next_cursor);
    assert.equal(plan({action:"inspect",work_ref:state.work_ref,sections:["overview"]}).revision,revisionBeforeBrowsing);
    // A browser-local resource failure must stay at that image's position.
    const assetURL = await page.locator("img").first().getAttribute("src");
    await page.route(assetURL, route=>route.fulfill({status:503,headers:{"Retry-After":"1"},contentType:"application/json",body:'{"error":"view_resource_busy"}'}));
    await open(state.view.revision_uri,1); await page.locator("summary").click();
    await page.getByText("资源繁忙，重新展开可重试。",{exact:true}).waitFor();
    assert.equal(await page.getByText("图片无法读取",{exact:true}).count(),0);
    await page.unroute(assetURL);
    await page.locator("summary").click(); await page.locator("summary").click(); await images();
    await page.screenshot({path:cfg.root+"/resource-busy-recovered.png"});
    await page.route(assetURL, route=>route.abort("failed"));
    await open(state.view.revision_uri,1); await page.locator("summary").click();
    await page.locator(".missing").waitFor();
    assert.equal(await page.locator(".missing").count(),1);
    await page.waitForFunction(()=>[...document.images].some(i=>i.naturalWidth>0));
    // Only this asset transport failed; a successful current probe keeps the
    // page online and the affected image retryable.
    assert.equal(await page.locator("#notice").isVisible(),false);
    assert.equal(await page.locator('.missing[data-temporary="true"]').count(),1);
    await page.screenshot({path:cfg.root+"/image-failure.png"});
    await page.unroute(assetURL);
    // Actual missing prepared bytes, then restoration, only in this generated Dataset.
    const ref=new URL(assetURL).searchParams.get("ref");
    const evidence=await (await fetch(state.view.current_uri+"/evidence?revision="+encodeURIComponent(state.revision)+"&ref="+encodeURIComponent(ref))).json();
    const assetPath=evidence.access.locator.value, bytes=fs.readFileSync(assetPath);
    try {
      fs.unlinkSync(assetPath);
      await open(state.view.revision_uri,1); await page.locator("summary").click(); await page.locator(".missing").waitFor();
      assert.equal(plan({action:"inspect",work_ref:state.work_ref}).sections.view.status,"degraded");
    } finally { fs.writeFileSync(assetPath,bytes); }
    await open(state.view.revision_uri,1); await page.locator("summary").click(); await images();
    const many={...partial,groups:refs.slice(0,120).map((ref,i)=>({relative_path:i===0?["父","子"]:i===1?["父"]:i===2?[]:["分组",String(i)],members:{kind:"explicit",source_item_refs:[ref]},source_naming:naming}))};
    state=update(state,{organization_content:many}); await open(state.view.revision_uri,50);
    assert.equal(await page.locator("details.group details").count(),0);
    await page.locator("summary").nth(0).click(); await page.locator("summary").nth(1).click();
    assert.equal(await page.locator("details[open]").count(),2);
    await page.getByRole("button",{name:"继续浏览",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("details.group").length===100);
    assert.equal(await page.locator("details[open]").count(),2);
    await page.locator("summary").nth(0).click();
    assert.equal(await page.locator("details[open]").count(),1);
    assert(await page.locator("details.group").nth(1).getAttribute("open")!==null);
    await page.getByRole("button",{name:"继续浏览",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("details.group").length===120);
    const paths=await page.locator("summary > span:first-child").allTextContents();
    assert.deepEqual(paths,many.groups.map(g=>g.relative_path.join(" / ")||many.logical_root));
    assert.equal(await page.getByRole("button",{name:"继续浏览",exact:true}).isVisible(),false);
    await page.screenshot({path:cfg.root+"/groups.png"});
    await page.setViewportSize({width:390,height:844});
    await page.evaluate(()=>scrollTo(0,0));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal((await page.locator(".gallery").first().evaluate(e=>getComputedStyle(e).gridTemplateColumns)).split(" ").length,1);
    await page.screenshot({path:cfg.root+"/narrow.png"});
    await page.setViewportSize({width:1440,height:1050});
    // A transient continuation failure retries the same cursor without duplication.
    await open(state.view.revision_uri,50);
    await page.route("**/page?**",route=>route.request().url().includes("cursor=")?route.fulfill({status:503,contentType:"application/json",body:'{"error":"view_resource_unavailable"}'}):route.continue());
    await page.getByRole("button",{name:"继续浏览",exact:true}).click(); await page.getByText("分组读取失败，请重试。",{exact:true}).waitFor();
    assert.equal(await page.locator("details.group").count(),50);
    await page.unroute("**/page?**"); await page.getByRole("button",{name:"重试读取",exact:true}).click();
    await page.waitForFunction(()=>document.querySelectorAll("details.group").length===100);
    const staleView=state.view, oldPage=await api(staleView,"groups");
    state=update(state,{working_notes:"新版本"});
    await page.getByRole("button",{name:"继续浏览",exact:true}).click();
    await page.locator("#notice").filter({hasText:"方案已有新版本"}).waitFor();
    assert.equal(await page.locator("details.group").count(),100);
    assert.equal((await api(staleView,"groups",oldPage.value.next_cursor)).status,409);
    assert.equal((await fetch(assetURL)).status,409);
    await page.screenshot({path:cfg.root+"/stale.png"});
    await page.locator("#current").click(); await page.waitForFunction(()=>document.querySelectorAll("details.group").length===50);
    assert.equal(page.url(),currentEntry);
    state=update(state,{organization_content:null}); await open(state.view.revision_uri,0);
    state=update(state,{organization_content:candidate}); await open(state.view.revision_uri,1);
    assert.equal(plan({action:"inspect",work_ref:state.work_ref}).candidate_content_identity,identity);
    const blocked=cfg.root+"/not-a-directory";fs.writeFileSync(blocked,"fixture");
    const request={action:"update",work_ref:state.work_ref,base_revision:state.revision,request_id:"request:delivery-failure",working_notes:"已保存，页面恢复测试"};
    const failed=plan(request,null,{...cfg.env,MEDIASENSE_DATA_HOME:blocked}); assert.equal(failed.outcome,"ok"); assert.equal(failed.view.status,"unavailable");
    const recovered=plan(request); assert.equal(recovered.revision,failed.revision); assert.equal(recovered.view.status,"ready"); state=recovered;
    assert.equal(cli(["views","stop","--json"]).state,"stopped");
    const restarted=plan({action:"inspect",work_ref:state.work_ref}); state.view=restarted.sections.view;
    await open(state.view.revision_uri,1); await page.locator("summary").click(); await images();
    assert.deepEqual(jsErrors,[]);
    fs.writeFileSync(cfg.root+"/browser-report.json",JSON.stringify({work_ref:state.work_ref,revision:state.revision,browser:"Chromium",member_count:names.length,member_pages:memberPages,group_count:120,group_pages:3,default_collapsed:true,independent_groups:true,ordered_flat_paths:true,lazy_images:true,horizontal_images:true,narrow_no_overflow:true,current_entry_reload:true,exact_entry_stays_pinned:true,save_failure_recovery:true,image_failure_recovery:true,host_restart:true,stale_page_cursor_asset:true,continuation_retry:true,source_safe:true,js_errors:jsErrors},null,2));
  } catch(e) {
    await page.screenshot({path:cfg.root+"/failure.png",fullPage:true}).catch(()=>{}); throw e;
  } finally {
    fs.writeFileSync(cfg.root+(process.argv[3]==="frozen"?"/frozen-browser-trace.json":"/cli-trace.json"),JSON.stringify(trace,null,2)); await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
