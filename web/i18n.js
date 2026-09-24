/* UI translations only. Source identifiers, expressions and evidence stay unchanged. */
(function (root) {
  "use strict";
  const en = {
    "ESP-IDF 错误码索引":"ESP-IDF Error Code Index",
    "ESP-IDF 错误码空间":"ESP-IDF Error Code Space",
    "错误码空间":"Error code space",
    "← 错误码空间":"← Error code space",
    "数据与方法":"Data and methods",
    "数据与方法 ↗":"Data and methods ↗",
    "数据与方法 · ESP-IDF 错误码索引":"Data and Methods · ESP-IDF Error Code Index",
    "主导航":"Main navigation",
    "查看 ESP-IDF 生态中已有的错误码定义，了解区段分布，核对你计划使用的 BASE。":"Browse observed ESP-IDF error code definitions, inspect their distribution and check a proposed BASE.",
    "社区观察，不分配号码。浅色区段仅表示当前索引未观察到使用，不保证可用。":"Unofficial observations, not an allocation service. Light segments indicate no observed use in this index; availability is not guaranteed.",
    "正在读取错误码索引…":"Loading error code index…",
    "正在读取索引…":"Loading index…",
    "索引概览":"Index overview",
    "个已收录组件":"indexed components",
    "个已定义数值":"defined values",
    "组数值重叠":"overlap groups",
    "了解收录范围与限制 ↗":"Coverage and limitations ↗",
    "区段查询":"Range lookup",
    "输入计划使用的起点与数量，查询区段内已有的错误码及 BASE 标记。":"Enter a start value and count to find observed error codes and BASE markers in that range.",
    "起点 / BASE":"Start / BASE",
    "数值数量":"Value count",
    "检查区段 ↗":"Check range ↗",
    "错误码分布":"Error code distribution",
    "显示范围":"Display range",
    "完整数值空间":"Full value space",
    "高度按区段大小压缩，非线性比例。点击区段查看组件与具体错误码；空洞保留，不将整个 BASE 区间视为占用。":"Segment heights use a compressed, nonlinear scale. Select a segment for components and definitions. Gaps remain visible; BASE markers do not reserve the following range.",
    "图例":"Legend",
    "已有错误码":"Defined error codes",
    "BASE / 边界标记":"BASE / boundary marker",
    "公共返回值":"Common return values",
    "数值重叠":"Numeric overlap",
    "未观察到使用":"No observed use",
    "定位数值、组件或符号":"Find a value, component or symbol",
    "例如 0x1101、nvs_flash、ESP_ERR_WIFI_BASE":"e.g. 0x1101, nvs_flash, ESP_ERR_WIFI_BASE",
    "区段 / 色带":"Range / band",
    "状态与组件":"Status and components",
    "可选择的错误码区段":"Selectable error code ranges",
    "继续显示区段":"Show more ranges",
    "选择一个区段":"Select a range",
    "点击左侧色带，查看已知定义。":"Select a band to inspect observed definitions.",
    "使用范围与限制":"Scope and limitations",
    "没有查询到重叠，也需要结合你所使用的组件版本与配置判断。本索引不预留号码，也不会将查询的区段登记为你的组件所有。":"A result with no overlap still requires checking your component versions and configuration. This index does not reserve numbers or assign queried ranges to components.",
    "查看数据来源、版本与方法说明 ↗":"Sources, versions and methodology ↗",
    "ESP-IDF ERROR INDEX · 非官方社区项目":"ESP-IDF ERROR INDEX · Unofficial community project",
    "下载完整索引 JSON ↗":"Download full index JSON ↗",
    "下载索引 JSON ↗":"Download index JSON ↗",
    "查看收录版本、文件筛选方式、解析状态和逐条定义。":"Inspect indexed versions, file selection, parsing status and individual definitions.",
    "这是有限来源的静态观察；不证明所有配置下的实际占用，也不分配或保留号码。":"Static observations from a limited set of sources; not proof of usage under every configuration. No numbers are allocated or reserved.",
    "扫描覆盖":"Scan coverage",
    "组件覆盖":"Component coverage",
    "只展示配置清单中选定的版本":"Only versions selected in the source configuration",
    "完成扫描不代表所有定义均可求值。来源读取失败时保留旧结果；数据接受时间仅在版本或分析结果更新时变化。":"A completed scan does not mean every definition can be evaluated. Previous results are retained on read failures; acceptance dates change only when a version or analysis changes.",
    "组件 / 版本":"Component / version",
    "维护方":"Maintainer",
    "扫描状态":"Scan status",
    "定义 / 未解析":"Definitions / unresolved",
    "接受时间":"Accepted on",
    "证据":"Evidence",
    "查询定义":"Definition lookup",
    "符号、组件或数值":"Symbol, component or value",
    "解析状态":"Resolution",
    "全部":"All",
    "已解析":"Resolved",
    "带条件":"Conditional",
    "未解析":"Unresolved",
    "可配置":"Configurable",
    "定义 / 组件":"Definition / component",
    "数值":"Value",
    "角色 / 状态":"Role / status",
    "表达式与来源":"Expression and source",
    "再显示 100 条":"Show 100 more",
    "重叠记录":"Overlap records",
    "待结合项目配置及来源关系复核":"Review with project configuration and source relationships",
    "按源码静态候选定义建立索引。默认排除测试、示例及内嵌 managed_components；不分析第三方构建执行结果。":"Indexed from static candidate definitions in source code. Tests, examples and nested managed_components are excluded by default. Third-party builds are not executed or analyzed.",
    "BASE 与边界角色可能由命名推断。配置表达式未求值时，不参与数值重叠比较。":"BASE and boundary roles may be inferred from names. Unevaluated configuration expressions are excluded from numeric overlap checks.",
    "已声明 BASE":"Declared BASE",
    "边界标记":"Boundary marker",
    "存在数值重叠":"Numeric overlap",
    "{0} 个数值":"{0} values",
    "十进制 {0} 至 {1}":"Decimal {0} to {1}",
    "当前收录的定义未落入此区段。它可以作为进一步核对的候选，但并非已确认空闲。":"No indexed definitions fall within this range. It is a candidate for further checking, not confirmed free space.",
    "用这个起点检查区段":"Check a range from this start",
    "这是已知的起点或边界标记；它本身不代表后续整段数值均已占用。":"This is an observed BASE or boundary marker. It does not imply that the entire following range is occupied.",
    "多个独立候选定义使用相同数值。是否会在你的项目中发生冲突，还取决于来源关系、版本与配置。":"Multiple independent candidate definitions use the same value. A conflict in your project depends on source relationships, versions and configuration.",
    "相关组件":"Related components",
    "Espressif 维护":"Maintained by Espressif",
    "社区组件":"Community component",
    "{0} · {1}":"{0} · {1}",
    "区段内的定义":"Definitions in this range",
    "别名":"Alias",
    "有生效条件":"Conditional",
    "数值可配置":"Configurable value",
    "最近保留的历史结果":"Retained previous result",
    "查看来源 ↗":"View source ↗",
    "此处显示前 100 条，共 {0} 条。完整记录见数据页。":"Showing the first 100 of {0} definitions. See the data page for all records.",
    "数据依据与收录范围 ↗":"Evidence and coverage ↗",
    "{0} 个匹配区段 · 清空搜索可恢复完整分布":"{0} matching ranges · Clear search to restore the full distribution",
    "{0} · {1} 个连续区段":"{0} · {1} contiguous ranges",
    "非负低位区间":"Low nonnegative range",
    "32 位有符号整数空间":"Signed 32-bit integer space",
    "没有找到匹配区段。可输入十六进制数值，或前往数据页查询尚不能定位的定义。":"No matching ranges. Try a hexadecimal value, or use the data page to inspect definitions with unresolved values.",
    "没有匹配区段":"No matching ranges",
    "查询完整定义与来源 ↗":"All definitions and sources ↗",
    "当前收录 {0} 个组件的选定版本，范围仍在扩充。":"Selected versions of {0} components are indexed. Coverage is still expanding.",
    "发现 {0} 个已定义数值或标记":"Found {0} defined values or markers",
    "当前索引未发现已定义数值重叠":"No overlap with defined values found in this index",
    "此结果不是可用性保证。仍需核对未收录组件、版本差异与可配置 BASE。":"This is not an availability guarantee. Check unindexed components, version differences and configurable BASE values.",
    "另有 {0} 条定义暂时不能定位到数值，未计入本次比较。":"{0} other definitions have unresolved values and are excluded from this comparison.",
    "在图中查看第一个已知数值":"Show the first observed value on the map",
    "在图中定位起点":"Show the start on the map",
    "暂时无法读取索引，请稍后刷新。":"Unable to load the index. Please refresh later.",
    "请输入 32 位有符号整数范围内的 BASE，可使用十进制或 0x 十六进制。":"Enter a BASE within the signed 32-bit range, using decimal or 0x hexadecimal notation.",
    "数量须为正整数，且区段不能超出 32 位有符号数值空间。":"The count must be a positive integer and the range must fit within the signed 32-bit value space.",
    "已扫描":"Scanned",
    "待扫描":"Pending",
    "预算延期":"Deferred by budget",
    "读取失败":"Read failed",
    "人工校正":"Reviewed",
    "公共值":"Common value",
    "错误码":"Error code",
    "已排除":"Excluded",
    "索引读取失败":"Index load failed",
    "已加载接受的数据快照 · 静态候选扫描 · 页面不发起上游扫描":"Accepted snapshot loaded · Static candidate scan · This page does not scan upstream sources",
    "配置中的组件":"Configured components",
    "完成文件扫描":"Completed file scans",
    "已发现定义":"Observed definitions",
    "待解析定义":"Unresolved definitions",
    "尚无结果":"No result yet",
    "{0} 条解析诊断":"{0} parser diagnostics",
    "{0} · {1}/{2} 个文件":"{0} · {1}/{2} files",
    "详细 JSON ↗":"Detailed JSON ↗",
    "{0} 条匹配":"{0} matches",
    "{0} · {1}{2}":"{0} · {1}{2}",
    "旧结果":"Previous result",
    "· 旧结果":"· Previous result",
    "未扫描子模块：{0}":"Unscanned submodules: {0}",
    "公共头文件依据：{0}":"Shared context headers: {0}",
    "公共定义：{0}":"Shared definition: {0}",
    " · 旧结果":" · Previous result",
    "· 可配置":"· Configurable",
    "解析依据":"Resolution details",
    "条件：":"Conditions: ",
    "关联 BASE：":"Related BASE: ",
    "未求值":"Not evaluated",
    "没有匹配的已观察定义；这不表示该数值未被使用。":"No matching observed definitions; this does not imply the value is unused.",
    "条件性数值重叠":"Conditional numeric overlap",
    "参与比较的已解析定义中暂未发现数值重叠。未解析项仍需复核。":"No numeric overlaps found among the resolved definitions compared. Unresolved definitions still require review.",
    "无法加载索引。请通过 HTTP 预览或检查 Pages 部署。":"Unable to load the index. Preview over HTTP or check the Pages deployment.",
    "ESP_ERR_NVS_BASE、nvs_flash、0x1101…":"ESP_ERR_NVS_BASE, nvs_flash, 0x1101…"
  };
  function translate(text, args = [], lang = "zh") {
    if (typeof text !== "string") return text;
    const trimmed = text.trim();
    const translated = lang === "en" && Object.hasOwn(en, trimmed) ? text.replace(trimmed, () => en[trimmed]) : text;
    return translated.replace(/\{(\d+)\}/g, (match, i) => i < args.length ? String(translate(args[i], [], lang)) : match);
  }
  const zh = Object.fromEntries(Object.entries(en).map(([key,value])=>[value,key]));
  function localizePage(text, lang) {
    if (typeof text !== "string" || lang !== "zh") return text;
    const trimmed = text.trim();
    return Object.hasOwn(zh, trimmed) ? text.replace(trimmed, () => zh[trimmed]) : text;
  }
  function selectLanguage(requested, saved, languages = []) {
    if (["en","zh"].includes(requested)) return requested;
    if (["en","zh"].includes(saved)) return saved;
    for (const language of languages) {
      const primary = typeof language === "string" ? language.toLowerCase().split(/[-_]/)[0] : "";
      if (["en","zh"].includes(primary)) return primary;
    }
    return "en";
  }
  if (typeof module !== "undefined" && module.exports) {module.exports = {translate, localizePage, selectLanguage, en}; return;}
  const url = new URL(location.href);
  let saved;
  try {saved = localStorage.getItem("errindex-language");} catch (_) { /* Storage may be blocked. */ }
  const requested = url.searchParams.get("lang");
  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  const lang = selectLanguage(requested, saved, languages);
  root.I18n = {lang, t:(text, ...args) => translate(text, args, lang)};
  document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
  document.title = localizePage(document.title, lang);
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let current;
  while ((current = walker.nextNode())) {
    if (!["SCRIPT","STYLE"].includes(current.parentElement?.tagName)) current.nodeValue = localizePage(current.nodeValue, lang);
  }
  for (const element of document.querySelectorAll("[aria-label], [placeholder], [title]")) {
    for (const name of ["aria-label","placeholder","title"]) if (element.hasAttribute(name)) element.setAttribute(name, localizePage(element.getAttribute(name), lang));
  }
  // Explicit language also works when browser storage is unavailable.
  for (const anchor of document.querySelectorAll('a[href="./"], a[href="diagnostics.html"]')) {
    const target = new URL(anchor.getAttribute("href"), location.href);target.searchParams.set("lang", lang);anchor.href = target.href;
  }
  const select = document.getElementById("language");select.value = lang;
  select.addEventListener("change", () => {
    try {localStorage.setItem("errindex-language", select.value);} catch (_) {}
    url.searchParams.set("lang", select.value);location.assign(url.href);
  });
})(globalThis);
