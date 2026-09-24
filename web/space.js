/* Sparse interval arithmetic: never iterate over the 32-bit number space. */
(function (root) {
  "use strict";
  const MIN = -2147483648, MAX = 2147483647;
  const hex = value => value < 0 ? "-0x" + (-value).toString(16).toUpperCase() : "0x" + value.toString(16).toUpperCase().padStart(4, "0");
  const roleState = records => {
    if (records.some(x => x.role === "error")) {
      const independent = records.filter(x => x.role === "error" && !x.alias_of);
      const identities = new Set(independent.map(x => [x.symbol,x.expression,x.source_url,x.file].join("\0")));
      return identities.size > 1 ? "overlap" : "occupied";
    }
    if (records.some(x => x.role === "base")) return "base";
    if (records.some(x => x.role === "shared")) return "shared";
    return "marker";
  };
  function segments(definitions, min = MIN, max = MAX) {
    const points = new Map();
    for (const record of definitions) {
      if (!Number.isInteger(record.value) || record.value < min || record.value > max || record.role === "excluded") continue;
      if (!points.has(record.value)) points.set(record.value, []);
      points.get(record.value).push(record);
    }
    const rows = []; let cursor = min;
    for (const [value, records] of [...points].sort((a,b)=>a[0]-b[0])) {
      if (value > cursor) rows.push({start:cursor,end:value-1,state:"unobserved",components:[],records:[]});
      const state = roleState(records), components = [...new Set(records.map(x=>x.component))].sort();
      const signature = JSON.stringify([state,components]);
      const previous = rows[rows.length-1];
      if (previous && previous.end === value-1 && previous.signature === signature) {
        previous.end = value; previous.records.push(...records);
      } else rows.push({start:value,end:value,state,components,records:[...records],signature});
      cursor = value + 1;
    }
    if (cursor <= max) rows.push({start:cursor,end:max,state:"unobserved",components:[],records:[]});
    return rows;
  }
  function parseNumber(text) {
    text = text.trim();
    if (!/^-?(?:0x[0-9a-f]+|\d+)$/i.test(text)) return null;
    const sign = text.startsWith("-") ? -1 : 1;
    const value = sign * Number(text.replace(/^-/, ""));
    return Number.isSafeInteger(value) ? value : null;
  }
  function checkRange(definitions, baseText, countText) {
    const start = parseNumber(baseText), count = parseNumber(countText);
    if (start === null || start < MIN || start > MAX) return {error:"请输入 32 位有符号整数范围内的 BASE，可使用十进制或 0x 十六进制。"};
    if (count === null || count < 1 || count > 4294967296 || start + count - 1 > MAX) return {error:"数量须为正整数，且区段不能超出 32 位有符号数值空间。"};
    const end = start + count - 1;
    const matches = definitions.filter(x=>Number.isInteger(x.value) && x.value>=start && x.value<=end && x.role!=="excluded");
    return {start,end,matches,unlocated:definitions.filter(x=>x.value===null && x.role!=="excluded").length};
  }
  const height = segment => Math.min(158, 54 + Math.log2(segment.end-segment.start+1) * 3.2);
  const api = {MIN,MAX,hex,segments,parseNumber,checkRange,height};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.ErrorSpace = api;
})(typeof globalThis !== "undefined" ? globalThis : this);
