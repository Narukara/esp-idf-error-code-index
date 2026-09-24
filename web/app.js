"use strict";
const tr = I18n.t;
const $ = id => document.getElementById(id);
const node = (tag,text,className) => {const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;};
function link(text,url) {const e=node("a",text);try {const u=new URL(url,location.href);if(u.protocol==="https:" || u.origin===location.origin){if(u.origin===location.origin && /(?:\/|\.html)$/.test(u.pathname))u.searchParams.set("lang",I18n.lang);e.href=u.href;e.rel="noopener noreferrer";}}catch(_){}return e;}
const S = ErrorSpace;
const titles = {occupied:tr("已有错误码"),base:tr("已声明 BASE"),marker:tr("边界标记"),shared:tr("公共返回值"),overlap:tr("存在数值重叠"),unobserved:tr("未观察到使用")};
const rangeLabel = row => row.start===row.end ? S.hex(row.start) : `${S.hex(row.start)} — ${S.hex(row.end)}`;
const numberLabel = value => value.toLocaleString(I18n.lang === "en" ? "en-US" : "zh-CN");
let data, allRows=[], selectedKey=null, common=false, visibleLimit=80, matchedRows=[];
const key = row => `${row.start}:${row.end}`;
function details(row) {
  selectedKey=key(row);
  for(const button of document.querySelectorAll(".segment"))button.setAttribute("aria-pressed",String(button.dataset.key===selectedKey));
  $("detail-heading").textContent=rangeLabel(row);
  const body=$("detail-body");body.replaceChildren(node("span",titles[row.state],`badge ${row.state}`));
  body.append(node("p",tr("{0} 个数值" ,numberLabel(row.end-row.start+1))),node("p",tr("十进制 {0} 至 {1}" ,row.start,row.end),"hint"));
  if(row.state==="unobserved") {
    body.append(node("p",tr("当前收录的定义未落入此区段。它可以作为进一步核对的候选，但并非已确认空闲。")));
    const button=node("button",tr("用这个起点检查区段"),"primary");button.type="button";
    button.addEventListener("click",()=>{$("range-base").value=S.hex(row.start);$("range-count").value=String(Math.min(256,row.end-row.start+1));$("range-form").requestSubmit();$("range-result").scrollIntoView({behavior:"smooth",block:"center"});});body.append(button);
  } else {
    if(row.state==="base" || row.state==="marker")body.append(node("p",tr("这是已知的起点或边界标记；它本身不代表后续整段数值均已占用。")));
    if(row.state==="overlap")body.append(node("p",tr("多个独立候选定义使用相同数值。是否会在你的项目中发生冲突，还取决于来源关系、版本与配置。")));
    body.append(node("h4",tr("相关组件")));
    for(const id of row.components){const component=data.components.find(x=>x.id===id);const item=node("div",undefined,"component-item");item.append(link(id,component?.url || "diagnostics.html"),node("small",tr("{0} · {1}" ,component?.version || "",component?.maintainer==="espressif"?tr("Espressif 维护"):tr("社区组件"))));body.append(item);}
    body.append(node("h4",tr("区段内的定义")));
    const list=node("div",undefined,"definition-list");
    for(const record of row.records.slice(0,100)){
      const item=node("div",undefined,"definition-item");item.append(node("code",S.hex(record.value)),node("strong",record.symbol));
      const notes=[];if(record.role==="base")notes.push("BASE");if(record.alias_of)notes.push(tr("别名"));if(record.conditions?.length)notes.push(tr("有生效条件"));if(record.configurable)notes.push(tr("数值可配置"));if(record.stale)notes.push(tr("最近保留的历史结果"));
      if(notes.length)item.append(node("small",notes.join(" · ")));
      item.append(link(tr("查看来源 ↗"),record.source_url));list.append(item);
      for(const ref of record.context_references || [])item.append(link(tr("公共定义：{0}",ref.symbol),ref.source_url));
    }
    body.append(list);
    if(row.records.length>100)body.append(node("p",tr("此处显示前 100 条，共 {0} 条。完整记录见数据页。" ,row.records.length),"hint"));
  }
  body.append(link(tr("数据依据与收录范围 ↗"),"diagnostics.html"));
}
function renderMap() {
  const query=$("map-query").value.trim().toLowerCase(), numeric=S.parseNumber(query);
  matchedRows=allRows.filter(row=>!query || (numeric!==null ? numeric>=row.start&&numeric<=row.end : row.components.some(x=>x.toLowerCase().includes(query)) || row.records.some(x=>x.symbol.toLowerCase().includes(query))));
  const host=$("space-map");host.replaceChildren();
  $("search-status").textContent=query ? tr("{0} 个匹配区段 · 清空搜索可恢复完整分布" ,matchedRows.length) : tr("{0} · {1} 个连续区段" ,common?tr("非负低位区间"):tr("32 位有符号整数空间"),allRows.length);
  for(const row of matchedRows.slice(0,visibleLimit)) {
    const button=node("button",undefined,`segment ${row.state}`);button.type="button";button.dataset.key=key(row);button.setAttribute("aria-pressed",String(key(row)===selectedKey));
    button.style.minHeight=`${S.height(row)}px`;button.setAttribute("aria-label",`${rangeLabel(row)}，${titles[row.state]}，${row.components.join("、")}`);
    const address=node("span",undefined,"segment-address");address.append(node("code",S.hex(row.start)));if(row.start!==row.end)address.append(node("code",S.hex(row.end)));
    const strip=node("span",undefined,"segment-strip");strip.setAttribute("aria-hidden","true");
    const caption=node("span",undefined,"segment-caption");caption.append(node("strong",titles[row.state]),node("small",row.components.join(" · ") || tr("{0} 个数值" ,numberLabel(row.end-row.start+1))));
    button.append(address,strip,caption,node("span","↗","segment-arrow"));button.addEventListener("click",()=>{details(row);if(window.innerWidth<=700)$("segment-detail").scrollIntoView({behavior:"smooth",block:"start"});});host.append(button);
  }
  if(!matchedRows.length)host.append(node("p",tr("没有找到匹配区段。可输入十六进制数值，或前往数据页查询尚不能定位的定义。"),"empty"));
  $("more-segments").hidden=visibleLimit>=matchedRows.length;
  if(matchedRows.length && !matchedRows.some(row=>key(row)===selectedKey))details(matchedRows[0]);
  if(!matchedRows.length){$("detail-heading").textContent=tr("没有匹配区段");$("detail-body").replaceChildren(link(tr("查询完整定义与来源 ↗"),"diagnostics.html"));selectedKey=null;}
}
function changeView(value) {
  common=value;visibleLimit=80;
  allRows=S.segments(data.definitions,common?0:S.MIN,common?65535:S.MAX);
  $("view-full").setAttribute("aria-pressed",String(!common));$("view-common").setAttribute("aria-pressed",String(common));
  $("view-full").classList.toggle("selected",!common);$("view-common").classList.toggle("selected",common);renderMap();
}
async function start() {
  const response=await fetch(document.documentElement.dataset.indexUrl || "index.json");if(!response.ok)throw new Error("index unavailable");data=await response.json();
  $("status").textContent=tr("当前收录 {0} 个组件的选定版本，范围仍在扩充。" ,data.components.length);
  $("component-count").textContent=data.components.length;
  $("value-count").textContent=new Set(data.definitions.filter(x=>Number.isInteger(x.value)&&x.role!=="excluded").map(x=>x.value)).size;
  $("overlap-count").textContent=data.overlaps.length;
  $("map-query").addEventListener("input",()=>{visibleLimit=80;renderMap();});
  $("view-full").addEventListener("click",()=>changeView(false));$("view-common").addEventListener("click",()=>changeView(true));
  $("more-segments").addEventListener("click",()=>{visibleLimit+=80;renderMap();});
  $("range-form").addEventListener("submit",event=>{
    event.preventDefault();const result=S.checkRange(data.definitions,$("range-base").value,$("range-count").value), host=$("range-result");host.hidden=false;host.replaceChildren();
    if(result.error){host.className="range-result warn";host.append(node("p",tr(result.error)));return;}
    host.className="range-result"+(result.matches.length?" warn":"");
    host.append(node("strong",result.matches.length?tr("发现 {0} 个已定义数值或标记" ,new Set(result.matches.map(x=>x.value)).size) : tr("当前索引未发现已定义数值重叠")),node("p",rangeLabel(result)));
    if(result.matches.length)host.append(node("p",[...new Set(result.matches.map(x=>x.component))].join(" · ")));
    host.append(node("p",tr("此结果不是可用性保证。仍需核对未收录组件、版本差异与可配置 BASE。"),"hint"));
    if(result.unlocated)host.append(node("p",tr("另有 {0} 条定义暂时不能定位到数值，未计入本次比较。" ,result.unlocated),"hint"));
    const action=node("button",result.matches.length?tr("在图中查看第一个已知数值"):tr("在图中定位起点"));action.type="button";
    action.addEventListener("click",()=>{const value=result.matches.length ? result.matches.reduce((min,x)=>Math.min(min,x.value),S.MAX) : result.start;$("map-query").value=S.hex(value);changeView(false);$("map-heading").scrollIntoView({behavior:"smooth",block:"start"});});host.append(action);
  });
  changeView(false);
  const preferred=allRows.find(row=>row.state==="occupied");if(preferred)details(preferred);
}
start().catch(error=>{$("status").textContent=tr("暂时无法读取索引，请稍后刷新。");console.error(error);});
