const fs=require("fs"), cp=require("child_process"), assert=require("assert/strict");
const cfg=JSON.parse(fs.readFileSync(process.argv[2]));
cfg.env={...process.env,...cfg.env};
const {chromium}=require(cfg.playwright);
const trace=[];
let serial=0;
function cli(args,env=cfg.env){let stdout;try{stdout=cp.execFileSync(cfg.host,args,{env,encoding:"utf8",timeout:90000,maxBuffer:8*1024*1024});}catch(e){stdout=e.stdout;if(!stdout)throw e;}return JSON.parse(stdout);}
function plan(request,authority,env){const args=["tools","call","mediasense.plan.work","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify(request),"--json"];if(authority)args.push("--authority",JSON.stringify(authority));const value=cli(args,env).result;assert(value,"No Tool result");trace.push({request,response:value});return value;}
function update(state,fields,env){return plan({action:"update",work_ref:state.work_ref,base_revision:state.revision,request_id:"request:browser-"+(++serial),...fields},null,env);}
const receipt=v=>Object.fromEntries(Object.entries(v).filter(([k])=>k!=="view"));
(async()=>{
 const browser=await chromium.launch({executablePath:cfg.browser,headless:true,args:["--disable-background-networking","--disable-component-update","--disable-sync","--no-first-run"]});
 const context=await browser.newContext({viewport:{width:1440,height:1050}});const page=await context.newPage();
 const jsErrors=[];page.on("pageerror",e=>jsErrors.push(e.message));
 async function open(uri,text){await page.goto(uri);await page.getByText(text,{exact:false}).first().waitFor();await page.waitForFunction(()=>!document.body.innerText.includes("正在读取已保存规划"));}
 try {
  if(process.argv[3]==="frozen"){
   await open(process.argv[4],"已冻结 · 已明确接受");
   await page.getByText("实际冻结记录",{exact:true}).waitFor();
   await page.getByRole("heading",{name:"目录甲",exact:true}).waitFor();
   await page.getByText("这些成员已逐项交代；图像仅来自选定源素材。",{exact:true}).waitFor();
   await page.evaluate(()=>document.querySelectorAll("img").forEach(i=>i.loading="eager"));
   await page.waitForFunction(()=>document.images.length>0 && Array.from(document.images).every(i=>i.complete && i.naturalWidth>0));
   await page.screenshot({path:cfg.root+"/frozen.png",fullPage:true});assert.deepEqual(jsErrors,[]);return;
  }
  let state=plan({action:"create",result_ref:cfg.result_ref,request_id:"request:browser-create"});assert.equal(state.outcome,"ok");assert.equal(state.view.status,"ready");
  await open(state.view.current_uri,"尚无已保存目录");
  const currentEntry=state.view.current_uri;
  assert.equal(page.url(),currentEntry);
  state=update(state,{working_notes:"先讨论方向 <script>throw new Error(123)</script>；其余尚未安排。"});
  await page.reload();
  await page.getByText("先讨论方向",{exact:false}).waitFor();
  assert.equal(page.url(),currentEntry);
  assert((await page.locator("#binding").innerText()).includes(state.revision));
  const exactPage=await context.newPage();
  const exactEntry=state.view.revision_uri;
  await exactPage.goto(exactEntry);
  await exactPage.getByText("先讨论方向",{exact:false}).waitFor();
  assert.deepEqual(jsErrors,[]);
  const scope={kind:"precheck_relation",origin:cfg.result_ref,relation:"accounts_for",direction:"outbound"};
  const resolved=cli(["tools","call","mediasense.precheck.read","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify({action:"resolve",dataset_ref:cfg.dataset_ref,result_ref:cfg.result_ref,source_set:scope,page:{limit:1000}}),"--json"]).result;
  const refs=resolved.members.slice(0,5).map(x=>x.source_item_ref);
  const partial={kind:"draft",result_ref:cfg.result_ref,scope,logical_root:"合成素材整理",groups:[{relative_path:["目录甲"],members:{kind:"explicit",source_item_refs:refs},source_naming:{default:"preserve_source_basename"}}],other_outcomes:[],decision_notes:[]};
  state=update(state,{organization_content:partial});assert.equal(state.outcome,"ok");
  await page.locator("#notice").filter({hasText:"规划已有新版本"}).waitFor();
  assert((await page.locator("#status").innerText()).includes("尚无已保存目录"));
  await page.reload();
  await page.getByText("已安排 5 / 1200 项，待安排 1195 项",{exact:false}).waitFor();
  assert.equal(page.url(),currentEntry);
  assert((await page.locator("#binding").innerText()).includes(state.revision));
  await exactPage.reload();
  await exactPage.getByText("当前页面不可用",{exact:true}).waitFor();
  assert.equal(exactPage.url(),exactEntry);
  assert.equal(await exactPage.locator("article.directory").count(),0);
  await exactPage.close();
  await page.screenshot({path:cfg.root+"/partial.png",fullPage:true});
  const oldURL=state.view.revision_uri;
  const review=cli(["tools","call","mediasense.precheck.read","--source",cfg.source,"--workspace",cfg.workspace,"--request",JSON.stringify({action:"review",dataset_ref:cfg.dataset_ref,result_ref:cfg.result_ref}),"--json"]).result;
  const evidenceRefs=review.items.slice(0,2).map(x=>x.evidence_ref);
  const candidate={...partial,kind:"candidate",groups:[{...partial.groups[0],members:scope}],decision_notes:[{summary:"这些成员已逐项交代；图像仅来自选定源素材。",applies_to:scope,evidence_refs:evidenceRefs}]};
  let full=update(state,{organization_content:{...candidate,kind:"draft"}});await open(full.view.revision_uri,"草案 · 尚未最终确认");
  state=update(full,{organization_content:candidate});assert.equal(state.outcome,"ok");await open(state.view.revision_uri,"完整候选 · 待明确接受");
  const group=page.locator("article").filter({has:page.getByRole("heading",{name:"目录甲",exact:true})}).first();
  await group.getByText("展开成员（1200 项）",{exact:true}).click();
  const members=group.locator("details").filter({has:page.locator("summary",{hasText:"展开成员（1200 项）"})});
  await members.getByText("已显示 50 / 1200").waitFor();
  let clicks=0;
  while(await members.getByRole("button",{name:"继续浏览",exact:true}).isVisible()){
   await members.getByRole("button",{name:"继续浏览",exact:true}).click();clicks++;
   await page.waitForFunction(expected=>Array.from(document.querySelectorAll("article details p")).some(p=>p.textContent.includes("已显示 "+expected+" / 1200")),Math.min(1200,(clicks+1)*50));
  }
  const names=await members.locator(".member-name").allTextContents();assert.equal(names.length,1200);assert.equal(new Set(names).size,1200);assert(names.includes("item-1199.jpg"));assert.equal(clicks,23);
  // Open a note scope through actual page controls too.
  const noteSection=page.locator("section").filter({has:page.getByRole("heading",{name:"决定说明与适用范围（1）",exact:true})});
  await noteSection.getByText("展开成员（1200 项）",{exact:true}).click();await noteSection.getByText("已显示 50 / 1200").waitFor();
  const evidenceRef=evidenceRefs[0];
  await noteSection.getByText("查看证据 · "+evidenceRef,{exact:true}).click();
  await page.waitForFunction(()=>Array.from(document.images).some(i=>i.naturalWidth>0));
  const evidence=await (await fetch(state.view.current_uri+"/evidence?revision="+encodeURIComponent(state.revision)+"&ref="+encodeURIComponent(evidenceRef))).json();
  const assetPath=evidence.access.locator.value, assetBytes=fs.readFileSync(assetPath);
  fs.unlinkSync(assetPath);
  await open(state.view.revision_uri,"完整候选 · 待明确接受");
  await page.getByText("查看证据 · "+evidenceRef,{exact:true}).last().click();
  await noteSection.locator(".missing").first().waitFor();
  assert.match(await noteSection.locator(".missing").first().innerText(), /图片不可读|证据不可读/);
  assert.match(await page.locator("#status").innerText(), /完整候选/);
  assert.equal(cli(["views","stop","--json"]).state,"stopped");
  const missingAfterRestart=plan({action:"inspect",work_ref:state.work_ref});
  assert.equal(missingAfterRestart.sections.view.status,"degraded");
  state.view=missingAfterRestart.sections.view;
  fs.writeFileSync(assetPath,assetBytes);
  await open(state.view.revision_uri,"完整候选 · 待明确接受");
  await page.getByText("查看证据 · "+evidenceRef,{exact:true}).last().click();
  await page.waitForFunction(()=>Array.from(document.images).some(i=>i.naturalWidth>0));
  const inspected=plan({action:"inspect",work_ref:state.work_ref});const identity=inspected.candidate_content_identity;
  const authority={principal_ref:"human:synthetic-review",work_ref:state.work_ref,reviewed_revision:state.revision,confirmed_content_identity:identity,confirmed_at:"2026-09-13T09:00:00Z"};
  const seal=current=>({action:"seal",work_ref:current.work_ref,revision:current.revision,candidate_content_identity:identity,request_id:"request:rejected-"+(++serial)});
  // Preserve an old continuation, then change only notes.
  const endpoint=state.view.current_uri+"/page?revision="+encodeURIComponent(state.revision)+"&collection=group%3A0";
  const oldPage=await (await fetch(endpoint)).json();
  await page.locator("section").filter({has:page.getByRole("heading",{name:"决定说明与适用范围（1）",exact:true})}).getByText("展开成员（1200 项）",{exact:true}).click();
  await page.getByText("已显示 50 / 1200").waitFor();
  const acceptedRevision=state.revision;state=update(state,{working_notes:"补充工作说明"});assert.equal(plan(seal(state),authority).error.code,"confirmation_binding_mismatch");
  await page.getByRole("button",{name:"继续浏览",exact:true}).last().click();await page.getByText(/已过期/).first().waitFor();
  assert.equal((await fetch(endpoint+"&cursor="+encodeURIComponent(oldPage.next_cursor))).status,409);
  await open(state.view.current_uri+"?revision="+encodeURIComponent(new URL(oldURL).searchParams.get("revision")),"当前页面不可用");
  // Same-value writes and withdrawal/restoration never revive the earlier acceptance.
  state=update(state,{working_notes:"补充工作说明"});assert.equal(plan(seal(state),authority).error.code,"confirmation_binding_mismatch");
  state=update(state,{organization_content:null});await open(state.view.revision_uri,"尚无已保存目录");
  state=update(state,{organization_content:candidate});assert.equal(plan({action:"inspect",work_ref:state.work_ref}).candidate_content_identity,identity);assert.equal(plan(seal(state),authority).error.code,"confirmation_binding_mismatch");
  // Successful save + failed view runtime directory, then safe replay through normal configuration.
  const blocked=cfg.root+"/not-a-directory";fs.writeFileSync(blocked,"fixture");
  const request={action:"update",work_ref:state.work_ref,base_revision:state.revision,request_id:"request:delivery-failure",working_notes:"规划已保存；页面恢复测试"};
  const failed=plan(request,null,{...cfg.env,MEDIASENSE_DATA_HOME:blocked});assert.equal(failed.outcome,"ok");assert.equal(failed.view.status,"unavailable");
  const recovered=plan(request);assert.deepEqual(receipt(recovered),receipt(failed));assert(["ready","degraded"].includes(recovered.view.status));state=recovered;
  await open(state.view.current_uri,"页面恢复测试");
  const replayOld=plan(trace.find(x=>x.request.organization_content?.kind==="draft").request);assert.equal(replayOld.view.status,"superseded");
  // Stop the real process; next ordinary inspect restores an entry and revision.
  const firstHost=cli(["views","status","--json"]);assert.equal(firstHost.state,"running");
  assert.equal(cli(["views","stop","--json"]).state,"stopped");
  const restarted=plan({action:"inspect",work_ref:state.work_ref});assert.equal(restarted.revision,state.revision);
  assert.notEqual(cli(["views","status","--json"]).instance,firstHost.instance);
  await open(restarted.sections.view.current_uri,"完整候选 · 待明确接受");
  // Browser access isolation: unknown handle, cross-origin, path-like resource input.
  const current=restarted.sections.view.current_uri;
  assert.equal((await fetch(current+"/overview",{headers:{Origin:"https://unrelated.invalid"}})).status,403);
  assert.equal((await fetch(current.replace(/[^/]+$/,"unknown")+"/overview")).status,404);
  assert.notEqual((await fetch(current+"/asset?revision="+encodeURIComponent(state.revision)+"&ref="+encodeURIComponent("/etc/passwd"))).status,200);
  await page.screenshot({path:cfg.root+"/candidate.png",fullPage:true});
  // A separate synthetic Work exercises derived parents, direct membership at
  // a parent/root, duplicate leaf names and shared parents across group pages.
  const hierarchyRefs=resolved.members.slice(0,54).map(x=>x.source_item_ref);
  const paths=[["父乙","子二","叶后"],["父甲","同名"],["父乙","子一"],["父乙"],["父甲","子三","同名"],[]];
  for(let i=6;i<50;i++)paths.push(["分页集合","分组 "+i]);
  paths.push(["父乙","子二","叶前"],["父甲","同名","末级"],["分页集合","分组 52"],["最后一层"]);
  let hierarchy=plan({action:"create",result_ref:cfg.result_ref,request_id:"request:hierarchy-create"});
  hierarchy=update(hierarchy,{organization_content:{kind:"candidate",result_ref:cfg.result_ref,
   scope:{kind:"explicit",source_item_refs:hierarchyRefs},logical_root:"多级目录审阅",
   groups:paths.map((path,i)=>({relative_path:path,members:{kind:"explicit",source_item_refs:[hierarchyRefs[i]]},source_naming:{default:"preserve_source_basename"}})),other_outcomes:[]}});
  assert.equal(hierarchy.outcome,"ok");await open(hierarchy.view.current_uri,"已安排 54 / 54 项");
  const hierarchySection=page.locator("section").filter({has:page.getByRole("heading",{name:"已保存目录（54）",exact:true})});
  await hierarchySection.getByText("已显示 50 / 54",{exact:true}).waitFor();
  async function treeRows(){return page.locator(".directory-tree article.directory").evaluateAll(nodes=>nodes.map(n=>({
   path:JSON.parse(n.dataset.path),parent:n.parentElement.closest("article.directory")?.dataset.path??null,
   total:n.querySelector(":scope > .directory-total").textContent,
   direct:n.querySelector(":scope > .directory-own").textContent,
   children:Array.from(n.querySelector(":scope > .directory-children").children).map(c=>JSON.parse(c.dataset.path))
  })));}
  let rows=await treeRows();
  assert.equal(rows[0].total,"包含 54 项");
  assert.equal(rows.find(r=>JSON.stringify(r.path)===JSON.stringify(["父乙"])).total,"包含 4 项");
  assert(!rows.some(r=>r.path.at(-1)==="叶前"));
  await hierarchySection.getByRole("button",{name:"继续浏览",exact:true}).click();
  await hierarchySection.getByText("已显示 54 / 54 · 已到末尾",{exact:true}).waitFor();
  rows=await treeRows();
  assert.equal(new Set(rows.map(r=>JSON.stringify(r.path))).size,rows.length);
  const row=path=>rows.find(r=>JSON.stringify(r.path)===JSON.stringify(path));
  assert.deepEqual(row([]).children,[["父乙"],["父甲"],["分页集合"],["最后一层"]]);
  assert.deepEqual(row(["父乙"]).children,[["父乙","子二"],["父乙","子一"]]);
  assert.deepEqual(row(["父乙","子二"]).children,[["父乙","子二","叶后"],["父乙","子二","叶前"]]);
  assert.equal(row(["父甲","同名","末级"]).parent,JSON.stringify(["父甲","同名"]));
  assert.equal(row(["父甲","子三","同名"]).parent,JSON.stringify(["父甲","子三"]));
  assert.match(row(["父乙"]).direct,/直属素材 1 项/);
  assert.match(row([]).direct,/直属素材 1 项/);
  const leafIndex=rows.findIndex(r=>JSON.stringify(r.path)===JSON.stringify(["父乙","子二","叶前"]));
  const leaf=page.locator(".directory-tree article.directory").nth(leafIndex);
  await leaf.getByText("展开成员（1 项）",{exact:true}).click();
  await leaf.getByText("已显示 1 / 1 · 已到末尾",{exact:true}).waitFor();
  assert.equal(await leaf.locator(".member-name").count(),1);
  const parentIndex=rows.findIndex(r=>JSON.stringify(r.path)===JSON.stringify(["父乙"]));
  await page.locator(".directory-tree article.directory").nth(parentIndex).screenshot({path:cfg.root+"/hierarchy.png"});
  assert.deepEqual(jsErrors,[]);
  fs.writeFileSync(cfg.root+"/browser-report.json",JSON.stringify({work_ref:state.work_ref,revision:state.revision,browser:"Chromium",member_count:names.length,member_pages:clicks+1,current_entry_reload:true,exact_entry_stays_pinned:true,hierarchy_groups:54,hierarchy_group_pages:2,hierarchy_depth:3,hierarchy_shared_parents:true,strict_confirmation_rejections:3,save_failure_recovery:true,image_failure_recovery:true,host_restart:true,stale_page_and_cursor:true,source_safe:true,acceptedRevision},null,2));
 }catch(e){await page.screenshot({path:cfg.root+"/failure.png",fullPage:true}).catch(()=>{});throw e;}finally{fs.writeFileSync(cfg.root+(process.argv[3]==="frozen"?"/frozen-browser-trace.json":"/cli-trace.json"),JSON.stringify(trace,null,2));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
