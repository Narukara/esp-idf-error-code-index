"""File selection without executing CMake or project code."""
import posixpath
import re
import shlex
from pathlib import PurePosixPath

SELECTION_VERSION = "1"
MODES = {"headers", "public-headers", "full"}


def is_header(path):
    return PurePosixPath(path).suffix in (".h", ".hpp")


def is_metadata(path):
    name = PurePosixPath(path).name
    return name.startswith("Kconfig") or name in ("CMakeLists.txt", "idf_component.yml")


def select_files(paths, read, mode="headers"):
    """Return selected file contents plus a transparent selection record.

    read is lazy: for GitHub, unselected source files are never downloaded;
    for Registry, unselected ZIP members are never decompressed.
    """
    if mode not in MODES:
        raise ValueError("Unknown scan mode: " + mode)
    paths = sorted(paths)
    headers = {path for path in paths if is_header(path)}
    files = {path: read(path) for path in paths if is_metadata(path)}
    roots, explicit, reasons = set(), set(), []
    found_public = False
    for path, text in list(files.items()):
        if not path.endswith("CMakeLists.txt"):
            continue
        text = re.sub(r"#\[\[.*?\]\]", "", text, flags=re.S)
        text = re.sub(r"(?m)#.*$", "", text)
        for match in re.finditer(r"\b(idf_component_register|idf_define_esp_err_codes)\s*\((.*?)\)", text, re.S | re.I):
            try:
                tokens = shlex.split(match[2], posix=True)
            except ValueError:
                reasons.append("unreadable_cmake_arguments")
                continue
            section = None
            for token in tokens:
                if re.fullmatch(r"[A-Z][A-Z_]+", token):
                    section = token
                    if token in ("INCLUDE_DIRS", "HEADERS"):
                        found_public = True
                    continue
                if section not in ("INCLUDE_DIRS", "HEADERS"):
                    continue
                if any(x in token for x in ("$", "<", ">", "\\", ":")) or token.startswith("/"):
                    reasons.append("dynamic_or_external_cmake_path")
                    continue
                for part in token.split(";"):
                    target = posixpath.normpath(posixpath.join(posixpath.dirname(path), part))
                    if target == ".." or target.startswith("../"):
                        reasons.append("external_cmake_path")
                    elif section == "INCLUDE_DIRS":
                        roots.add(target)
                    else:
                        explicit.add(target)
    public = {path for path in headers if any(root == "." or path.startswith(root.rstrip("/") + "/") for root in roots)} | (headers & explicit)
    if explicit - headers:
        reasons.append("registered_header_missing_or_generated")
    if mode == "full":
        selected = set(paths)
    elif mode == "headers":
        selected = headers
    elif not found_public or reasons or not public:
        selected = headers
        reasons.append("fallback_all_headers")
    else:
        selected = public
    pending = set(selected) - files.keys()
    while pending:
        path = min(pending)
        pending.remove(path)
        content = files[path] = read(path)
        if mode != "public-headers" or "fallback_all_headers" in reasons:
            continue
        # Follow every branch's literal includes inside this component. Ambiguous
        # basenames are all included; outside dependencies remain unresolved.
        for include in re.finditer(r'(?m)^\s*#\s*include\s*([<"])([^>"\n]+)[>"]', content):
            name = include[2]
            relative = posixpath.normpath(posixpath.join(posixpath.dirname(path), name))
            matches = {p for p in headers if p == relative or p == name or p.endswith("/" + name)}
            pending.update(matches - files.keys())
        if re.search(r'(?m)^\s*#\s*include\s+[^<"\s]', content):
            reasons.extend(["dynamic_header_include", "fallback_all_headers"])
            pending.update(headers - files.keys())
    return files, {"version": SELECTION_VERSION, "mode": mode, "candidate_files": len(paths),
                   "selected_files": len(files), "skipped_files": len(paths) - len(files),
                   "public_header_candidates": sorted(public), "reasons": sorted(set(reasons)),
                   "coverage_note": "Public headers are a static CMake approximation; private implementation definitions may be absent"}
