import io
import hashlib
import re
import stat
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote

from .network import SourceError
from .storage import digest
from .selection import select_files

EXCLUDED = {"test", "tests", "test_apps", "host_test", "host_tests", "unit-test-app", "examples", ".git", "managed_components", "node_modules"}


def wanted(path):
    p = PurePosixPath(path)
    return (not any(x in EXCLUDED for x in p.parts)
            and (p.suffix in (".h", ".hpp", ".c", ".cpp") or p.name.startswith("Kconfig")
                 or p.name in ("CMakeLists.txt", "idf_component.yml")))


def stable_key(version):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)(?:~(\d+))?", version)
    return tuple(int(x or 0) for x in match.groups()) if match else None


def inspect_source(source, client):
    if source["kind"] == "registry":
        component = source["component"]
        metadata = client.json("https://components.espressif.com/api/components/" + component)
        versions = [x for x in metadata["versions"] if not x.get("yanked_at")]
        selection = source.get("version", "latest-stable")
        if selection == "latest-stable":
            versions = [x for x in versions if stable_key(x["version"]) is not None]
            versions.sort(key=lambda x: stable_key(x["version"]), reverse=True)
        else:
            versions = [x for x in versions if x["version"] == selection]
        if not versions:
            raise SourceError("No matching non-yanked version: " + component)
        version = versions[0]
        return {"kind": "registry", "version": version["version"], "component_hash": version["component_hash"],
                "archive_url": version["url"], "component_url": f"https://components.espressif.com/components/{component}/versions/{version['version']}",
                "repository_url": version.get("repository"), "dependencies": version.get("dependencies", []),
                "targets": version.get("targets", [])}
    repository, ref = source["repository"], source["ref"]
    commit = client.json(f"https://api.github.com/repos/{repository}/commits/{quote(ref, safe='')}",
                         immutable=bool(re.fullmatch(r"[a-f0-9]{40}", ref)))
    return {"kind": "github", "version": ref, "commit": commit["sha"], "root_tree": commit["commit"]["tree"]["sha"],
            "repository_url": "https://github.com/" + repository,
            "component_url": f"https://github.com/{repository}/tree/{commit['sha']}/{source['path']}"}


def read_archive(body, limits, mode="full", with_selection=False):
    files = {}
    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            entries = archive.infolist()
            if len(entries) > 20000:
                raise SourceError("Archive has too many entries")
            total, names, candidates = 0, set(), {}
            for entry in entries:
                path = PurePosixPath(entry.filename)
                if path.is_absolute() or ".." in path.parts or "\\" in entry.filename or ":" in entry.filename:
                    raise SourceError("Unsafe archive path")
                if stat.S_ISLNK(entry.external_attr >> 16):
                    raise SourceError("Archive symlinks are not supported")
                if entry.filename in names:
                    raise SourceError("Duplicate archive path")
                names.add(entry.filename)
                if entry.is_dir() or not wanted(entry.filename):
                    continue
                candidates[entry.filename] = entry
            def read(path):
                nonlocal total
                entry = candidates[path]
                total += entry.file_size
                if (entry.file_size > limits["max_file_bytes"] or total > limits["max_source_bytes"]
                        or len(files) >= limits["max_files"]):
                    raise SourceError("Component exceeds extraction limits; raise limits explicitly or narrow source")
                # Read selected members only; never extract paths or run package code.
                files[path] = archive.read(entry).decode("utf-8")
                return files[path]
            files, selection = select_files(candidates, read, mode)
    except (zipfile.BadZipFile, UnicodeDecodeError, RuntimeError) as exc:
        raise SourceError("Cannot read component archive: " + str(exc)) from exc
    return (files, selection) if with_selection else files


def download_source(source, identity, client):
    if source["kind"] == "registry":
        body = client.get(identity["archive_url"], cache_identity=identity["component_hash"])
        files, selection = read_archive(body, client.limits, source.get("scan_mode", "headers"), with_selection=True)
        return files, {"archive_sha256": digest(body),
                       "selection": selection,
                       "hash_note": "Registry component_hash identifies the release; archive_sha256 is independently observed, not compared as the same hash algorithm"}
    repository = source["repository"]
    tree = identity["root_tree"]
    base = f"https://api.github.com/repos/{repository}/git/trees/"
    for part in PurePosixPath(source["path"]).parts:
        listing = client.json(base + tree, immutable=True)
        entry = next((x for x in listing["tree"] if x["path"] == part and x["type"] == "tree"), None)
        if entry is None:
            raise SourceError("Missing component directory: " + source["path"])
        tree = entry["sha"]
    listing = client.json(base + tree + "?recursive=1", immutable=True)
    if listing.get("truncated"):
        raise SourceError("Truncated GitHub tree; scan not accepted")
    submodules = [x for x in listing["tree"] if x["type"] == "commit"]
    excluded = set(source.get("exclude_submodules", []))
    if any(x["path"] not in excluded for x in submodules):
        raise SourceError("Component contains submodules; configure their pinned sources separately")
    entries = [x for x in listing["tree"] if x["type"] == "blob" and wanted(x["path"])]
    entries = {source["path"].rstrip("/") + "/" + x["path"]: x for x in entries}
    files, total = {}, 0
    def read(path):
        nonlocal total
        entry = entries[path]
        client.check_time()
        if entry.get("mode") == "120000" or entry.get("size", 0) > client.limits["max_file_bytes"]:
            raise SourceError("Unsupported symlink or oversized source file")
        if len(files) >= client.limits["max_files"] or total + entry.get("size", 0) > client.limits["max_source_bytes"]:
            raise SourceError("Selected source files exceed component limits")
        url = f"https://raw.githubusercontent.com/{repository}/{identity['commit']}/{quote(path, safe='/')}"
        body = client.get(url, immutable=True)
        if len(body) > client.limits["max_file_bytes"]:
            raise SourceError("Oversized source file")
        blob_hash = hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()
        if blob_hash != entry["sha"]:
            raise SourceError("Downloaded Git blob does not match the pinned tree")
        total += len(body)
        if total > client.limits["max_source_bytes"]:
            raise SourceError("Selected source files exceed component size limit")
        files[path] = body.decode("utf-8")
        return files[path]
    files, selection = select_files(entries, read, source.get("scan_mode", "headers"))
    evidence = {"component_tree": tree, "selection": selection}
    context_paths = source.get("context_headers", [])
    for path in context_paths:
        # Resolve and verify against this component's exact commit, not a moving dependency.
        current = identity["root_tree"]
        parts = PurePosixPath(path).parts
        for index, part in enumerate(parts):
            listing = client.json(base + current, immutable=True)
            if listing.get("truncated"):
                raise SourceError("Truncated context header tree")
            entry = next((x for x in listing["tree"] if x["path"] == part), None)
            expected = "blob" if index == len(parts) - 1 else "tree"
            if not entry or entry["type"] != expected:
                raise SourceError("Missing context header: " + path)
            current = entry["sha"]
        entries[path] = entry
        read(path)
    if context_paths:
        evidence["context_headers"] = list(context_paths)
    if submodules:
        evidence["excluded_submodules"] = [{"path": x["path"], "commit": x["sha"]} for x in submodules]
    return files, evidence


def discover(client, page):
    result = client.json(f"https://components.espressif.com/api/components?page={page}")
    if not isinstance(result, list):
        raise SourceError("Unexpected Registry discovery schema")
    return [{"id": f"{x['namespace']}/{x['name']}", "kind": "registry",
             "component": f"{x['namespace']}/{x['name']}", "version": "latest-stable",
             "maintainer": "unknown", "error_pattern": "^ESP_ERR_"} for x in result]
