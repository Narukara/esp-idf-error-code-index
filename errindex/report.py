import html
import json
import shutil
from collections import defaultdict
from pathlib import Path

from .storage import digest, read_json, write_json


def collect(root):
    manifest = read_json(root / "data/manifest.json", {"sources": {}})
    configured = read_json(root / "config/sources.json")["sources"]
    active = {x["id"] for x in configured}
    components, codes, buckets = [], [], defaultdict(list)
    for source in configured:
        entry = manifest["sources"].get(source["id"], {})
        result = read_json(root / entry["result"]) if entry.get("result") else None
        component = {"id": source["id"], "status": entry.get("status", "pending"),
                     "error": entry.get("error"), "accepted_at": entry.get("accepted_at"),
                     "maintainer": source.get("maintainer", "unknown"), "definitions": 0,
                     "unresolved": 0, "values": [], "bases": [], "version": None,
                     "configurable": 0, "diagnostics": 0}
        if result:
            component["version"] = result["identity"]["version"]
            component["url"] = result["identity"]["component_url"]
            component["diagnostics"] = len(result["analysis"]["diagnostics"])
            component["coverage"] = result["analysis"]["coverage"]
            component["result"] = entry["result"]
            component["selection"] = result.get("evidence", {}).get("selection")
            component["excluded_submodules"] = result.get("evidence", {}).get("excluded_submodules", [])
            component["context_headers"] = result.get("evidence", {}).get("context_headers", [])
            for definition in result["analysis"]["definitions"]:
                record = {**definition, "component": source["id"], "version": component["version"],
                          "stale": component["status"] != "ok"}
                codes.append(record)
                component["definitions"] += 1
                if record["resolution"] == "unresolved":
                    component["unresolved"] += 1
                if record["configurable"]:
                    component["configurable"] += 1
                if record["role"] == "base":
                    component["bases"].append({"symbol": record["symbol"], "value": record["value"],
                                               "expression": record["expression"]})
                if record["role"] == "error" and record["value"] is not None:
                    component["values"].append(record["value"])
                    buckets[record["value"]].append(record)
            component["values"] = sorted(set(component["values"]))
        components.append(component)
    overlaps = []
    for value, definitions in sorted(buckets.items()):
        # Aliases of an existing symbol represent reuse, not an independent claim.
        independent = [x for x in definitions if not x.get("alias_of")]
        identities = {(x["symbol"], x["expression"], x["source_url"], x["file"]) for x in independent}
        if len(identities) < 2:
            continue
        classification = "conditional-overlap" if any(x["conditions"] for x in independent) else "numeric-overlap"
        overlaps.append({"value": value, "hex": hex(value), "classification": classification,
                         "definitions": [{k: x[k] for k in ("component", "version", "symbol", "file", "line", "source_url", "stale")}
                                         for x in independent],
                         "note": "Coexistence, shared origin and semantic independence require review; not a confirmed project conflict"})
    return {"schema_version": 1, "notice": "非官方观察索引，不分配或保留错误码。未观察到不代表可安全使用。",
            "scope": "Only configured component versions; static candidate definitions, not compiled/runtime usage",
            "components": components, "definitions": codes, "overlaps": overlaps,
            "inactive_sources": sorted(set(manifest["sources"]) - active)}


def cell(value):
    return html.escape(str(value)).replace("|", "&#124;").replace("\n", " ")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8", newline="\n")


def report(root):
    data = collect(root)
    write_json(root / "data/index.json", data)
    lines = ["# ESP-IDF 错误码观察报告", "", data["notice"], "",
             "仅包含配置清单中的版本；`ok` 表示文件读取完成，不代表所有表达式均可求值或已确认构建生效。",
             "历史结果保存在 data/components；此表只展示各来源最后接受的结果。失败时保留旧结果。", "",
             "| 组件 | 版本 | 状态 | 定义数 | 未解析 | 可配置 | 解析诊断 | 已定义数值包络 |",
             "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |"]
    for component in data["components"]:
        values = component["values"]
        envelope = f"{hex(min(values))}…{hex(max(values))}（{len(values)} 个数值，可能有空洞）" if values else "—"
        lines.append("| " + " | ".join(cell(x) for x in (component["id"], component["version"] or "—",
                     component["status"], component["definitions"], component["unresolved"], component["configurable"],
                     component["diagnostics"], envelope)) + " |")
    lines += ["", "未发现候选定义不代表不存在错误码。来源命名规则、生成代码和外部依赖可能影响覆盖。", ""]
    write_text(root / "reports/summary.md", "\n".join(lines))
    lines = ["# 数值重叠记录", "", "这里只报告静态候选数值重叠，不判定组件有缺陷或可在同一构建中共存。",
             "BASE、边界标记和直接别名不作为独立错误码计数。未解析的配置表达式不参与数值比较。", ""]
    if not data["overlaps"]:
        lines += ["当前已解析且参与比较的定义中未发现数值重叠。", ""]
    for item in data["overlaps"]:
        lines += [f"## {item['hex']} — {item['classification']}", ""]
        for definition in item["definitions"]:
            lines.append(f"- {cell(definition['component'])}@{cell(definition['version'])}: {cell(definition['symbol'])} — {cell(definition['file'])}:{definition['line']}")
        lines.append("")
    write_text(root / "reports/overlaps.md", "\n".join(lines))
    return data


def build(root, output):
    data = collect(root)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "i18n.js", "app.js", "space.js", "style.css", "atlas.css", "diagnostics.html", "diagnostics.js"):
        shutil.copyfile(root / "web" / name, output / name)
    write_json(output / "index.json", data)
    # Cache keys keep freshly deployed HTML, scripts and observation data consistent.
    assets = ("app.js", "space.js", "i18n.js", "diagnostics.js", "style.css", "atlas.css", "index.json")
    urls = {name: name + "?v=" + digest((output / name).read_bytes())[:16] for name in assets}
    for name in ("index.html", "diagnostics.html"):
        page = (root / "web" / name).read_text(encoding="utf-8")
        page = page.replace('<html lang="en">', '<html lang="en" data-index-url="' + urls["index.json"] + '">')
        for asset, url in urls.items():
            page = page.replace('src="' + asset + '"', 'src="' + url + '"')
            page = page.replace('href="' + asset + '"', 'href="' + url + '"')
        write_text(output / name, page)
    # Expose exact accepted evidence files for download without copying source archives.
    for component in data["components"]:
        if component.get("result"):
            destination = output / component["result"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / component["result"], destination)
    write_text(output / ".nojekyll", "")


def diff(old_path, new_path):
    old, new = read_json(old_path, {"components": [], "definitions": [], "overlaps": []}), read_json(new_path)
    old_components = {x["id"]: x for x in old["components"]}
    changes = [x["id"] for x in new["components"] if x != old_components.get(x["id"])]
    old_defs = {(x["component"], x["symbol"], x["file"], x["expression"], x["value"]) for x in old["definitions"]}
    new_defs = {(x["component"], x["symbol"], x["file"], x["expression"], x["value"]) for x in new["definitions"]}
    return "\n".join(["更新已配置组件的错误码观察数据与报告。", "",
                       f"- 变化组件：{', '.join(changes) or '无'}",
                       f"- 新增/变化定义：{len(new_defs - old_defs)}；移出当前视图定义：{len(old_defs - new_defs)}",
                       f"- 重叠组：{len(old['overlaps'])} → {len(new['overlaps'])}",
                       f"- 未解析定义：{sum(x['resolution'] == 'unresolved' for x in new['definitions'])}",
                       "", "已运行离线测试、数据校验和 Pages 构建。旧版本观察记录继续保留。", ""])
