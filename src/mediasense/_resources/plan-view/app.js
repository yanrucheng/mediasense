"use strict";
const base = location.pathname.replace(/\/$/, "");
let revision = new URLSearchParams(location.search).get("revision");
let state, logicalRoot, stale = false;
const content = document.querySelector("#content"), notice = document.querySelector("#notice");
document.querySelector("#current").href = base;
function node(tag, text, parent) { const n = document.createElement(tag); if (text !== undefined) n.textContent = text; if (parent) parent.append(n); return n; }
function message(text) { notice.hidden = false; notice.textContent = text; }
function url(action, args={}) { const q = new URLSearchParams(args); if (revision) q.set("revision", revision); return base + "/" + action + "?" + q; }
async function read(action, args={}) {
  const response = await fetch(url(action,args), {cache:"no-store"});
  const value = await response.json();
  if (!response.ok) {
    if (response.status === 409) { stale=true; message("这份规划已有新版本。当前页面保留原版本；请点击“查看当前版本”重新审阅。"); }
    throw new Error(value.message || (response.status===409 ? "此版本已过期，不能继续拼接成员。" : value.error));
  }
  return value;
}
function details(parent, label, text) { const d=node("details",undefined,parent); node("summary",label,d); if(text!==undefined)node("pre",text,d); return d; }
function members(parent, collection, total) {
  const d=details(parent, "展开成员（"+total+" 项）");
  d.addEventListener("toggle",()=>{if(d.open && !d.dataset.loaded){d.dataset.loaded="1";pages(d,collection,member);}});
}
function member(item,parent) {
  const li=node("li",undefined,parent); node("span",item.name,li).className="member-name";
  node("span",item.path,li).className="path";
  if(item.target_name)node("p","目标文件名："+item.target_name,li);
  details(li,"来源与条件",JSON.stringify({source_item_ref:item.source_item_ref,qualifications:item.qualifications,observations:item.observations},null,2));
}
function image(parent,ref,label,available=true) {
  const figure=node("figure",undefined,parent);
  if(ref && available) {
    const link=node("a",undefined,figure);link.href=url("asset",{ref});link.target="_blank";link.rel="noopener";link.setAttribute("aria-label","打开准备图片："+label);
    const img=node("img",undefined,link);img.alt=label;img.loading="lazy";img.src=link.href;
    node("span","打开准备图片",link);
    img.addEventListener("error",()=>{link.remove();node("p","图片不可读：准备图片缺失、格式不支持或访问失败；来源保留如下。",figure).className="missing";message("页面规划仍可查看；部分图片不可读，请查看对应占位说明。");});
  } else node("p","图片不可读：未取得可读的本地准备图片。",figure).className="missing";
  node("figcaption",label+(ref ? " · "+ref : ""),figure);return figure;
}
function evidence(parent,ref) {
  const d=details(parent,"查看证据 · "+ref);d.className="evidence";
  d.addEventListener("toggle",async()=>{if(!d.open||d.dataset.loaded)return;d.dataset.loaded="1";
    try { const value=await read("evidence",{ref});image(d,ref,"证据实际来源见下方",!value.error);node("pre",JSON.stringify(value,null,2),d); }
    catch(e){node("p","证据不可读："+e.message,d).className="missing";}
  });
}
function group(item,parent) {
  // Reuse derived parents across group pages. Their order is first appearance
  // in the saved groups, including when a parent's own group arrives later.
  if(!parent.directoryNodes){parent.directoryNodes=new Map();parent.classList.add("directory-tree");}
  let directory, container=parent;
  for(let depth=0;depth<=item.relative_path.length;depth++){
    const path=item.relative_path.slice(0,depth), key=JSON.stringify(path);
    directory=parent.directoryNodes.get(key);
    if(!directory){
      const article=node("article",undefined,container);article.className="directory";article.dataset.path=key;
      node("h"+Math.min(6,depth+3),depth===0?logicalRoot:path[depth-1],article);
      const count=node("p",undefined,article);count.className="count directory-total";
      const own=node("div",undefined,article);own.className="directory-own";
      const children=node("div",undefined,article);children.className="directory-children";
      directory={article,count,own,children};parent.directoryNodes.set(key,directory);
    }
    directory.count.textContent="包含 "+item.path_totals[depth]+" 项";
    container=directory.children;
  }
  const a=directory.own;node("p","直属素材 "+item.total+" 项",a);
  for(const s of item.samples||[]) {image(a,s.evidence_ref,s.label,s.available);if(s.evidence_ref)evidence(a,s.evidence_ref);}
  members(a,item.collection,item.total);
}
function outcome(item,parent) { const a=node("article",undefined,parent);node("h3",({retain_current_organization:"保留原处",exclude_from_logical_organization:"排除于逻辑组织"})[item.outcome]||item.outcome,a);node("p",item.reason||"未附加说明",a);members(a,item.collection,item.total);for(const ref of item.evidence_refs||[])evidence(a,ref); }
function note(item,parent) { const a=node("article",undefined,parent);node("p",item.summary,a);members(a,item.collection,item.total);for(const ref of item.evidence_refs||[])evidence(a,ref); }
function pages(parent,collection,render) {
  const list=node(collection.includes(":")||collection==="unassigned"?"ol":"div",undefined,parent);
  const progress=node("p","",parent),button=node("button","加载",parent);let cursor=null,shown=0;
  async function load(){button.disabled=true;
    try { if(stale)throw new Error("本页已过期，请查看当前版本。");
      const p=await read("page",{collection,...(cursor?{cursor}:{})});for(const item of p.items)render(item,list);
      shown+=p.items.length;cursor=p.next_cursor;progress.textContent="已显示 "+shown+" / "+p.total+(p.complete?" · 已到末尾":"");
      button.hidden=p.complete;button.textContent="继续浏览";
    }catch(e){progress.textContent=e.message;button.textContent="重试读取";}finally{button.disabled=false;}
  }
  button.addEventListener("click",load);load();
}
async function start(){
  try {
    const value=await read("overview"); revision=value.revision;state=value.state;logicalRoot=value.logical_root;
    // Pin all reads in this loaded document without changing entry semantics.
    // Refreshing a current URI must resolve current state again; an exact URI
    // keeps its explicit revision and must never silently follow a newer one.
    document.querySelector("h1").textContent=value.logical_root;
    const summary=value.scope_summary;
    document.querySelector("#status").textContent=(state==="closed"?"已冻结 · 已明确接受":({none:"讨论中 · 尚无已保存目录",draft:"草案 · 尚未最终确认",candidate:"完整候选 · 待明确接受"})[value.organization_kind])+(summary?"；已安排 "+(summary.organized+summary.other_outcomes)+" / "+summary.scope+" 项，待安排 "+summary.unassigned+" 项":"");
    document.querySelector("#binding").textContent="Work "+value.work_ref+" · 版本 "+revision+" · Result "+value.result_ref;
    const coverage=node("section",undefined,content);node("h2","范围与完整性",coverage);
    node("p","Result 覆盖："+value.result.coverage+"；Plan 范围："+(summary?summary.scope+" 项":"尚未保存")+"。全部安排完也不表示已接受。",coverage);
    details(coverage,"Result 覆盖、来源和限制",JSON.stringify(value.result,null,2));
    const context=node("section",undefined,content);node("h2","工作说明与偏好",context);node("small","讨论上下文；不自动进入 Frozen Plan。",context);node("pre",value.working_notes||"尚无工作说明",context);details(context,"组织偏好",JSON.stringify(value.preferences,null,2));
    if(value.confirmation){const a=node("section",undefined,content);node("h2","实际冻结记录",a);node("pre",JSON.stringify(value.confirmation,null,2),a);}
    for(const [collection,title,render] of [["groups","已保存目录",group],["other_outcomes","其他明确处置",outcome],["decision_notes","决定说明与适用范围",note]]){
      const a=node("section",undefined,content);node("h2",title+"（"+value.counts[collection]+"）",a);pages(a,collection,render);
    }
    if(summary){const a=node("section",undefined,content);node("h2","待安排（"+summary.unassigned+" 项）",a);node("p",summary.unassigned?"这些素材尚无处置决定。":"当前范围内的素材均已有明确处置。",a);pages(a,"unassigned",member);}
    setInterval(async()=>{try{const current=await read("current");if(current.revision!==revision){stale=true;message("规划已有新版本。请点击“查看当前版本”；本页不会混入新版内容。");}else if(current.state!==state)message("此版本已有冻结记录。刷新页面查看实际记录。");}catch(e){message("当前版本检查不可用："+e.message);}},4000);
  }catch(e){document.querySelector("#status").textContent="当前页面不可用";message(e.message+" 已保存规划不会丢失；可通过 Tool 重新取得入口。");}
}
start();
