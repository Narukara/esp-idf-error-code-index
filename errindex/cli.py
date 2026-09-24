import argparse
import json
import re
from pathlib import Path

from .engine import scan
from .network import Client
from .report import build, diff, report
from .sources import discover
from .storage import read_json, write_json


def validate_config(config, overrides):
    if config.get("schema_version") != 1 or overrides.get("schema_version") != 1:
        raise ValueError("Unsupported configuration schema")
    limits = config["limits"]
    for key in ("max_components", "max_requests", "max_download_bytes", "max_response_bytes", "max_seconds",
                "metadata_ttl_seconds", "max_files", "max_file_bytes", "max_source_bytes", "cache_max_bytes"):
        if type(limits.get(key)) is not int or limits[key] <= 0:
            raise ValueError("Expected positive integer limit: " + key)
    if not isinstance(limits.get("request_interval_seconds"), (int, float)) or limits["request_interval_seconds"] < 0.25:
        raise ValueError("Minimum request interval is 0.25 seconds")
    ids = set()
    for source in config["sources"]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["id"]) or source["id"] in ids:
            raise ValueError("Invalid or duplicate source id")
        ids.add(source["id"])
        if source.get("scan_mode", "headers") not in ("headers", "public-headers", "full"):
            raise ValueError("Unknown scan_mode")
        exclusions = source.get("exclude_submodules", [])
        if (not isinstance(exclusions, list) or any(not isinstance(x, str) or not x
                or x.startswith("/") or ".." in x.split("/") or "\\" in x for x in exclusions)):
            raise ValueError("Invalid submodule exclusions")
        context_headers = source.get("context_headers", [])
        if (not isinstance(context_headers, list) or len(context_headers) > 8
                or any(not isinstance(x, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+\.h", x)
                       or ".." in x.split("/") or x.startswith("/")
                       or x.startswith(source.get("path", "") + "/") for x in context_headers)
                or (context_headers and source["kind"] != "github")):
            raise ValueError("Context headers must be explicit external .h paths in the same GitHub repository (at most 8)")
        if source["kind"] == "github":
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["repository"]):
                raise ValueError("Invalid GitHub repository")
            if not re.fullmatch(r"[A-Za-z0-9_./-]+", source["path"]) or ".." in source["path"].split("/") or source["path"].startswith("/"):
                raise ValueError("Invalid component path")
        elif source["kind"] == "registry":
            if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source["component"]):
                raise ValueError("Invalid Registry component")
        else:
            raise ValueError("Unknown source kind")
        re.compile(source.get("error_pattern", "^ESP_ERR_"))
        if source.get("maintainer") == "espressif" and not source.get("maintainer_evidence"):
            raise ValueError("Official-maintainer classification requires evidence")
    for rule in overrides["rules"]:
        for key in ("source", "version", "symbol", "file", "expression", "reason", "evidence"):
            if not rule.get(key):
                raise ValueError("Override must include " + key)
        if rule["source"] not in ids:
            raise ValueError("Override references an unconfigured source")
        if "value" in rule and (type(rule["value"]) is not int or not -(2**31) <= rule["value"] < 2**31):
            raise ValueError("Override value must fit signed 32 bits")
        if "role" in rule and rule["role"] not in ("base", "marker", "shared", "error", "excluded"):
            raise ValueError("Unknown override role")


def validate_data(root):
    manifest = read_json(root / "data/manifest.json", {"sources": {}})
    if manifest.get("schema_version", 1) != 1:
        raise ValueError("Unsupported manifest schema")
    for entry in manifest["sources"].values():
        for key, value in entry.get("analyses", {}).items():
            if not re.fullmatch(r"[a-f0-9]{64}", key) or not re.fullmatch(r"[a-f0-9]{64}", value):
                raise ValueError("Invalid analysis fingerprint")
        if not entry.get("result"):
            continue
        if not re.fullmatch(r"data/components/[a-f0-9]{64}\.json", entry["result"]):
            raise ValueError("Invalid result path")
        result = read_json(root / entry["result"])
        if not result or result["schema_version"] != 1 or result["fingerprint"] != entry["fingerprint"]:
            raise ValueError("Missing or inconsistent accepted result")
        if result["fingerprint"] != Path(entry["result"]).stem:
            raise ValueError("Result filename does not match fingerprint")
        for record in result["analysis"]["definitions"]:
            if record["line"] < 1 or (record["value"] is not None and type(record["value"]) is not int):
                raise ValueError("Invalid definition")
        if not re.fullmatch("[a-f0-9]{64}", result["source_sha256"]):
            raise ValueError("Invalid source digest")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Unofficial ESP-IDF error-code observation tools")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    update = commands.add_parser("scan")
    update.add_argument("--source", help="Only this configured component")
    update.add_argument("--offline", action="store_true")
    update.add_argument("--refresh", action="store_true", help="Revalidate cached metadata; respect all budgets")
    update.add_argument("--force", action="store_true", help="Reanalyze selected sources; respect all budgets")
    update.add_argument("--max-components", type=int)
    commands.add_parser("report")
    commands.add_parser("validate")
    site = commands.add_parser("build")
    site.add_argument("--output", type=Path)
    discovery = commands.add_parser("discover")
    discovery.add_argument("--page", type=int, default=1)
    changes = commands.add_parser("diff")
    changes.add_argument("--before", type=Path, required=True)
    resume_parser = commands.add_parser("resume-pending")
    resume_parser.add_argument("--ref", default="refs/remotes/origin/automation/observations")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config = read_json(root / "config/sources.json")
    overrides = read_json(root / "config/overrides.json")
    if args.command == "scan" and args.max_components is not None:
        config["limits"]["max_components"] = args.max_components
    validate_config(config, overrides)
    if args.command in ("scan", "report", "build"):
        validate_data(root)
    if args.command == "scan":
        result = scan(root, config, overrides, args.source, args.offline, args.refresh, args.force)
        report(root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if any(x["status"] == "failed" for x in result["items"]):
            raise SystemExit(2)
    elif args.command == "report":
        report(root)
    elif args.command == "validate":
        validate_data(root)
        print("Configuration and accepted data are valid.")
    elif args.command == "build":
        validate_data(root)
        build(root, args.output or root / "site")
    elif args.command == "discover":
        if args.page < 1:
            raise ValueError("Page must be positive")
        client = Client(root / ".cache/http", config["limits"])
        write_json(root / ".cache/discovered-sources.json", discover(client, args.page))
        print("Candidates saved to .cache/discovered-sources.json; review before adding to config/sources.json")
    elif args.command == "diff":
        print(diff(args.before, root / "data/index.json"))
    elif args.command == "resume-pending":
        from .resume import resume
        resume(root, args.ref)
        validate_data(root)
