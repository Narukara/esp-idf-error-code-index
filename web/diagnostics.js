"use strict";
const tr = I18n.t;
const $ = (id) => document.getElementById(id);
const node = (tag, text, className) => {
  const element = document.createElement(tag);
  if (text !== undefined) element.textContent = text;
  if (className) element.className = className;
  return element;
};
function link(text, url) {
  const element = node("a", text);
  try {
    const parsed = new URL(url, location.href);
    if (parsed.protocol === "https:" || parsed.origin === location.origin) {
      if(parsed.origin===location.origin && /(?:\/|\.html)$/.test(parsed.pathname))parsed.searchParams.set("lang",I18n.lang);element.href = parsed.href;
      element.rel = "noopener noreferrer";
    }
  } catch (_) { /* Untrusted metadata is shown as plain text. */ }
  return element;
}
const labels = {ok:tr("已扫描"), pending:tr("待扫描"), deferred:tr("预算延期"), failed:tr("读取失败"), resolved:tr("已解析"), conditional:tr("带条件"), unresolved:tr("未解析"), reviewed:tr("人工校正"), base:"BASE", marker:tr("边界标记"), shared:tr("公共值"), error:tr("错误码"), excluded:tr("已排除")};
async function start() {
  const response = await fetch(document.documentElement.dataset.indexUrl || "index.json");
  if (!response.ok) throw new Error(tr("索引读取失败"));
  const data = await response.json();
  $("status").textContent = tr("已加载接受的数据快照 · 静态候选扫描 · 页面不发起上游扫描");
  const stats = [[data.components.length,tr("配置中的组件")],[data.components.filter(x=>x.status === "ok").length,tr("完成文件扫描")],[data.definitions.length,tr("已发现定义")],[data.definitions.filter(x=>x.resolution === "unresolved").length,tr("待解析定义")]];
  for (const [number, title] of stats) {
    const item = node("div",undefined,"stat"); item.append(node("strong",number),node("span",title)); $("stats").append(item);
  }
  for (const component of data.components) {
    const row = node("tr"); const name = node("td");
    name.append(component.url ? link(component.id,component.url) : node("span",component.id),node("small",component.version || tr("尚无结果")));
    const status = node("td"); status.append(node("span",labels[component.status],"badge"+(component.status === "ok"?"":" warn")));
    if (component.error) status.append(node("small",component.error));
    if (component.excluded_submodules?.length) status.append(node("small",tr("未扫描子模块：{0}",component.excluded_submodules.map(x=>x.path).join(", "))));
    if (component.context_headers?.length) status.append(node("small",tr("公共头文件依据：{0}",component.context_headers.join(", "))));
    if (component.diagnostics) status.append(node("small",tr("{0} 条解析诊断" ,component.diagnostics)));
    if (component.selection) {
      status.append(node("small",tr("{0} · {1}/{2} 个文件" ,component.selection.mode,component.selection.selected_files,component.selection.candidate_files)));
      if (component.selection.reasons.length) status.append(node("small",component.selection.reasons.join(", ")));
    }
    const evidence = node("td"); if (component.result) evidence.append(link(tr("详细 JSON ↗"),component.result));
    row.append(name,node("td",component.maintainer === "espressif" ? "Espressif" : component.maintainer),status,node("td",`${component.definitions} / ${component.unresolved}`),node("td",component.accepted_at?.slice(0,10) || "—"),evidence); $("components").append(row);
  }
  let limit = 100;
  function render() {
    const query = $("query").value.trim().toLowerCase(), state = $("resolution").value;
    const numeric = /^(?:0x[0-9a-f]+|-?\d+)$/.test(query) ? Number(query) : null;
    const definitions = data.definitions.filter(x => (!query || (numeric !== null ? x.value === numeric : `${x.symbol} ${x.component} ${x.expression}`.toLowerCase().includes(query))) && (!state || (state === "configurable" ? x.configurable : x.resolution === state)));
    $("count").textContent = tr("{0} 条匹配" ,definitions.length); $("definitions").replaceChildren();
    for (const record of definitions.slice(0,limit)) {
      const row = node("tr"), name = node("td"), status = node("td"), source = node("td");
      name.append(node("code",record.symbol),node("small",tr("{0} · {1}{2}" ,record.component,record.version,record.stale ? tr(" · 旧结果") : "")));
      status.append(node("span",labels[record.role],"badge"),node("small",labels[record.resolution]+(record.configurable ? tr(" · 可配置") : "")));
      source.append(node("code",record.expression),node("br"),link(`${record.file}:${record.line}`,record.source_url));
      if (record.reason || record.conditions.length || record.base_symbols.length) {
        const detail = node("details");detail.append(node("summary",tr("解析依据")));
        if (record.reason) detail.append(node("small",record.reason));
        if (record.conditions.length) detail.append(node("small",tr("条件：")+record.conditions.join(" && ")));
        if (record.base_symbols.length) detail.append(node("small",tr("关联 BASE：")+record.base_symbols.join(", ")));
        for (const ref of record.context_references || []) detail.append(link(`${ref.symbol} · ${ref.file}:${ref.line}`,ref.source_url));
        source.append(detail);
      }
      row.append(name,node("td",record.hex ?? tr("未求值")),status,source); $("definitions").append(row);
    }
    if (!definitions.length) {const row=node("tr"),cell=node("td",tr("没有匹配的已观察定义；这不表示该数值未被使用。"),"empty");cell.colSpan=4;row.append(cell);$("definitions").append(row);}
    $("more").hidden = limit >= definitions.length;
  }
  $("query").addEventListener("input",()=>{limit=100;render();}); $("resolution").addEventListener("change",()=>{limit=100;render();}); $("more").addEventListener("click",()=>{limit+=100;render();}); render();
  for (const overlap of data.overlaps) {
    const item = node("div",undefined,"overlap"); item.append(node("strong",overlap.hex+" · "+(overlap.classification === "conditional-overlap" ? tr("条件性数值重叠") : tr("数值重叠"))));
    for (const record of overlap.definitions) item.append(node("small",`${record.component}@${record.version} · ${record.symbol}`));
    $("overlaps").append(item);
  }
  if (!data.overlaps.length) $("overlaps").append(node("p",tr("参与比较的已解析定义中暂未发现数值重叠。未解析项仍需复核。"),"empty"));
}
start().catch(error=>{$("status").textContent = tr("无法加载索引。请通过 HTTP 预览或检查 Pages 部署。"); console.error(error);});
