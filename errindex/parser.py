"""Conservative C constant extraction; unknown expressions stay unknown."""
import ast
import operator
import re

from .storage import digest

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.BitOr: operator.or_, ast.BitAnd: operator.and_, ast.BitXor: operator.xor,
       ast.LShift: operator.lshift, ast.RShift: operator.rshift}


class Unresolved(ValueError):
    pass


def evaluate(expression, lookup):
    if len(expression) > 4096:
        raise Unresolved("expression_too_large")
    expression = re.sub(r"\b(0[xX][0-9a-fA-F]+|[0-9]+)[uUlL]+\b", r"\1", expression)
    expression = re.sub(r"\b0([0-7]+)\b", r"0o\1", expression)
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except (SyntaxError, ValueError, RecursionError) as exc:
        raise Unresolved("unsupported_expression") from exc

    def visit(node, depth=0):
        if depth > 40:
            raise Unresolved("expression_too_deep")
        if isinstance(node, ast.Constant) and type(node.value) is int:
            value = node.value
        elif isinstance(node, ast.Name):
            value = lookup(node.id)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub, ast.Invert)):
            operand = visit(node.operand, depth + 1)
            value = {ast.UAdd: operator.pos, ast.USub: operator.neg, ast.Invert: operator.invert}[type(node.op)](operand)
        elif isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = visit(node.left, depth + 1), visit(node.right, depth + 1)
            if isinstance(node.op, (ast.LShift, ast.RShift)) and not 0 <= right <= 31:
                raise Unresolved("unsupported_shift")
            if isinstance(node.op, ast.RShift) and left < 0:
                raise Unresolved("implementation_defined_shift")
            value = OPS[type(node.op)](left, right)
        else:
            raise Unresolved("unsupported_expression")
        # Avoid inventing values for C unsigned wrapping or target-specific integer widths.
        if not -(2**31) <= value < 2**31:
            raise Unresolved("requires_C_integer_type_semantics")
        return value

    return visit(tree.body)


def strip_comments(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', lambda m: "\n" * m[0].count("\n"), text, flags=re.S)


def extract(files, pattern):
    definitions, configs, diagnostics = [], {}, []
    wanted = re.compile(pattern)
    for path, content in sorted(files.items()):
        if path.rsplit("/", 1)[-1].startswith("Kconfig"):
            for match in re.finditer(r"(?m)^\s*(?:menuconfig|config)\s+(\w+)\s*\n([\s\S]*?)(?=^\s*(?:menuconfig|config|endmenu|menu)\s|\Z)", content):
                configs["CONFIG_" + match[1]] = {"file": path, "line": content[:match.start()].count("\n") + 1,
                                                   "definition": match[0].strip()}
            continue
        if not path.endswith((".h", ".hpp", ".c", ".cpp")):
            continue
        cleaned = strip_comments(content)
        # Joining continued lines keeps physical line numbers stable through an explicit map.
        logical, start, pending = [], 1, ""
        for line_no, line in enumerate(cleaned.splitlines(), 1):
            if not pending:
                start = line_no
            pending += line.rstrip("\\") if line.endswith("\\") else line
            if line.endswith("\\"):
                pending += " "
                continue
            logical.append((start, pending))
            pending = ""
        stack, branch_history, condition_lines = [], [], {}
        guard_match = re.match(r"\s*#\s*ifndef\s+(\w+)\s*\n\s*#\s*define\s+\1\b", cleaned)
        guard = guard_match[1] if guard_match else None
        for line_no, line in logical:
            directive = re.match(r"\s*#\s*(if|ifdef|ifndef|elif|else|endif)\b(.*)", line)
            if directive:
                kind, arg = directive[1], directive[2].strip()
                if kind in ("if", "ifdef", "ifndef"):
                    expression = arg if kind == "if" else f"{'!' if kind == 'ifndef' else ''}defined({arg})"
                    if kind == "ifndef" and arg == guard and not stack:
                        expression = ""
                    stack.append(expression)
                    branch_history.append([expression])
                elif kind == "elif" and stack:
                    stack[-1] = f"!({' || '.join(branch_history[-1])}) && ({arg})"
                    branch_history[-1].append(arg)
                elif kind == "else" and stack:
                    stack[-1] = f"!({' || '.join(branch_history[-1])})"
                elif kind == "endif" and stack:
                    stack.pop()
                    branch_history.pop()
                continue
            condition_lines[line_no] = [x for x in stack if x and x != 'defined(__cplusplus)' and x != '!defined(__cplusplus)']
            match = re.match(r"\s*#\s*define\s+(\w+)(.*)", line)
            if match:
                name, rest = match[1], match[2]
                if rest.startswith("("):
                    if wanted.search(name):
                        diagnostics.append({"file": path, "line": line_no, "reason": "function_macro", "symbol": name})
                    continue
                if rest.strip():
                    definitions.append({"symbol": name, "expression": rest.strip(), "file": path,
                                        "line": line_no, "conditions": condition_lines[line_no], "syntax": "define"})
            undef = re.match(r"\s*#\s*undef\s+(\w+)", line)
            if undef:
                definitions.append({"symbol": undef[1], "expression": "<undefined>", "file": path,
                                    "line": line_no, "conditions": condition_lines[line_no], "syntax": "undef"})
        for enum in re.finditer(r"\benum(?:\s+\w+)?\s*\{([^{}]*)\}", cleaned):
            if re.search(r"(?m)^\s*#", enum[1]):
                diagnostics.append({"file": path, "line": cleaned[:enum.start()].count("\n") + 1,
                                    "reason": "enum_contains_preprocessor_directives"})
                continue
            previous, offset = None, enum.start(1)
            for item in enum[1].split(","):
                match = re.fullmatch(r"\s*(\w+)\s*(?:=\s*(.*?))?\s*", item, re.S)
                line_no = cleaned[:offset + len(item) - len(item.lstrip())].count("\n") + 1
                if match:
                    expression = match[2] or (previous + " + 1" if previous else "0")
                    definitions.append({"symbol": match[1], "expression": expression.strip(), "file": path,
                                        "line": line_no, "conditions": condition_lines.get(line_no, []), "syntax": "enum"})
                    previous = match[1]
                elif item.strip():
                    diagnostics.append({"file": path, "line": line_no, "reason": "unsupported_enum"})
                offset += len(item) + 1
    return definitions, configs, diagnostics


def analyze(files, pattern, overrides=(), context_headers=()):
    definitions, configs, diagnostics = extract(files, pattern)
    table = {}
    for definition in definitions:
        table.setdefault(definition["symbol"], []).append(definition)
    wanted = re.compile(pattern)

    def resolve(name, context, trail):
        if name in trail or len(trail) > 40:
            raise Unresolved("cyclic_or_deep_reference:" + name)
        if name.startswith("CONFIG_"):
            raise Unresolved("configuration_required:" + name)
        choices = table.get(name, [])
        applicable = [x for x in choices if not x["conditions"] or x["conditions"] == context]
        # Other conditional definitions may override an unconditional definition.
        if not applicable or any(x not in applicable for x in choices):
            raise Unresolved("missing_or_conditional_reference:" + name)
        expressions = {x["expression"] for x in applicable}
        if len(expressions) != 1:
            raise Unresolved("ambiguous_reference:" + name)
        return evaluate(next(iter(expressions)), lambda child: resolve(child, context, trail | {name}))

    records, matched_rules = [], set()
    for definition in definitions:
        name = definition["symbol"]
        if not wanted.search(name) or definition["syntax"] == "undef" or definition["file"] in context_headers:
            continue
        record = dict(definition)
        record["id"] = digest(definition)[:24]
        record["role"] = ("base" if name.endswith("_BASE") else "marker" if name.endswith(("_MAX", "_END", "_COUNT"))
                          else "shared" if name in ("ESP_OK", "ESP_FAIL") else "error")
        record["alias_of"] = definition["expression"] if re.fullmatch(r"[A-Za-z_]\w*", definition["expression"]) else None
        record["config_symbols"] = []
        seen = set()

        def dependencies(symbol):
            if symbol in seen or len(seen) > 1000:
                return
            seen.add(symbol)
            if symbol.startswith("CONFIG_"):
                record["config_symbols"].append(symbol)
            for entry in table.get(symbol, []):
                for child in re.findall(r"\b[A-Za-z_]\w*\b", entry["expression"]):
                    dependencies(child)

        dependencies(name)
        record["config_symbols"].sort()
        record["base_symbols"] = sorted(x for x in seen if x.endswith("_BASE") and x != name)
        references = [{k: item[k] for k in ("symbol", "file", "line", "expression")}
                      for symbol in sorted(seen) for item in table.get(symbol, [])
                      if item["file"] in context_headers]
        if references:
            record["context_references"] = references
        record["configurable"] = bool(record["config_symbols"])
        record["value"] = None
        try:
            record["value"] = evaluate(definition["expression"], lambda symbol: resolve(symbol, definition["conditions"], {name}))
            record["resolution"] = "conditional" if definition["conditions"] else "resolved"
        except Unresolved as exc:
            record["resolution"], record["reason"] = "unresolved", str(exc)
        for rule_index, rule in enumerate(overrides):
            if rule["symbol"] == name and rule["file"] == record["file"] and rule["expression"] == record["expression"]:
                matched_rules.add(rule_index)
                record["review"] = {"reason": rule["reason"], "evidence": rule["evidence"]}
                if "role" in rule:
                    record["role"] = rule["role"]
                if "value" in rule:
                    record["value"], record["resolution"] = rule["value"], "reviewed"
                if rule.get("exclude"):
                    record["role"] = "excluded"
        record["hex"] = hex(record["value"]) if record["value"] is not None else None
        records.append(record)
    for index, rule in enumerate(overrides):
        if index not in matched_rules:
            diagnostics.append({"file": rule["file"], "symbol": rule["symbol"], "reason": "unmatched_override"})
    families = []
    for base in (x for x in records if x["role"] == "base"):
        members = [x for x in records if base["symbol"] in x["base_symbols"] and x["role"] == "error"]
        values = sorted({x["value"] for x in members if x["value"] is not None})
        families.append({"base": base["symbol"], "expression": base["expression"], "value": base["value"],
                         "conditions": base["conditions"], "defined_values": values,
                         "envelope": [min(values), max(values)] if values else None,
                         "unresolved_members": [x["symbol"] for x in members if x["value"] is None],
                         "declared_reserved_range": None})
    registered_headers = []
    for path, content in files.items():
        if path.endswith("CMakeLists.txt"):
            for call in re.finditer(r"\bidf_define_esp_err_codes\s*\(([^)]*)\)", content, re.S):
                registered_headers.append({"file": path, "line": content[:call.start()].count("\n") + 1,
                                           "arguments": call[1].strip(), "interpretation": "literal call; CMake not evaluated"})
    return {"definitions": sorted(records, key=lambda x: (x["file"], x["line"], x["symbol"])),
            "configuration": configs, "diagnostics": diagnostics, "families": families,
            "registered_headers": registered_headers,
            "coverage": "candidate-static-scan",
            "limitations": ["Pattern-based candidate discovery; not a build or whole-program analysis",
                            "External includes, generated code, complex expressions and C type conversions may remain unresolved",
                            "Macro scope and conditional coexistence are not proven; enum preprocessing is conservative",
                            "BASE/MAX/END/COUNT roles are naming heuristics unless reviewed"]}
