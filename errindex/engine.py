from datetime import datetime, timezone

from . import PARSER_VERSION, SCHEMA_VERSION
from .network import BudgetExceeded, Client, SourceError
from .parser import analyze
from .sources import download_source, inspect_source
from .storage import digest, read_json, write_json
from .selection import SELECTION_VERSION


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def scan(root, config, overrides, only=None, offline=False, refresh=False, force=False):
    manifest_path = root / "data/manifest.json"
    manifest = read_json(manifest_path, {"schema_version": SCHEMA_VERSION, "sources": {}, "next_source": None})
    client = Client(root / ".cache/http", config["limits"], offline, refresh)
    sources = [x for x in config["sources"] if not only or x["id"] == only]
    if only and not sources:
        raise ValueError("Unknown source: " + only)
    if not only and manifest.get("next_source"):
        ids = [x["id"] for x in sources]
        if manifest["next_source"] in ids:
            offset = ids.index(manifest["next_source"])
            sources = sources[offset:] + sources[:offset]
    run = {"started_at": now(), "items": [], "budget_exhausted": False}
    attempts = 0
    for source in sources:
        if attempts >= config["limits"]["max_components"]:
            manifest["next_source"] = source["id"]
            run["budget_exhausted"] = True
            break
        attempts += 1
        entry = manifest["sources"].setdefault(source["id"], {})
        try:
            identity = inspect_source(source, client)
            rules = [r for r in overrides["rules"] if r["source"] == source["id"] and r["version"] == identity["version"]]
            input_fingerprint = digest({"source": source, "identity": identity, "parser": PARSER_VERSION,
                                  "selection": SELECTION_VERSION,
                                  "schema": SCHEMA_VERSION, "rules": rules})
            previous = entry.get("analyses", {}).get(input_fingerprint)
            result_path = root / "data/components" / ((previous or input_fingerprint) + ".json")
            if previous and result_path.exists() and not force:
                result = read_json(result_path)
                fingerprint = result["fingerprint"]
                status = "reused"
            else:
                files, evidence = download_source(source, identity, client)
                client.check_time()
                analysis = analyze(files, source.get("error_pattern", "^ESP_ERR_"), rules,
                                   context_headers=evidence.get("context_headers", []))
                client.check_time()
                fingerprint = digest({"input": input_fingerprint, "source": digest(files), "evidence": evidence})
                result_path = root / "data/components" / (fingerprint + ".json")
                result = {"schema_version": SCHEMA_VERSION, "parser_version": PARSER_VERSION,
                          "fingerprint": fingerprint, "input_fingerprint": input_fingerprint, "source": source, "identity": identity,
                          "source_sha256": digest(files), "evidence": evidence,
                          "files": [{"path": path, "sha256": digest(body.encode())} for path, body in sorted(files.items())],
                          "analysis": analysis}
                for definition in result["analysis"]["definitions"]:
                    if source["kind"] == "github":
                        definition["source_url"] = f"{identity['repository_url']}/blob/{identity['commit']}/{definition['file']}#L{definition['line']}"
                        for reference in definition.get("context_references", []):
                            reference["source_url"] = f"{identity['repository_url']}/blob/{identity['commit']}/{reference['file']}#L{reference['line']}"
                    else:
                        definition["source_url"] = identity["component_url"]
                write_json(result_path, result)
                status = "scanned"
            entry.setdefault("analyses", {})[input_fingerprint] = fingerprint
            entry.update({"result": result_path.relative_to(root).as_posix(), "status": "ok"})
            entry.pop("error", None)
            # Do not create repository churn on unchanged checks.
            if entry.get("fingerprint") != fingerprint:
                entry["accepted_at"] = now()
                entry["fingerprint"] = fingerprint
            run["items"].append({"source": source["id"], "status": status})
        except BudgetExceeded as exc:
            entry.update({"status": "deferred", "error": str(exc)})
            manifest["next_source"] = source["id"]
            run["budget_exhausted"] = True
            run["items"].append({"source": source["id"], "status": "deferred", "reason": str(exc)})
            break
        except (SourceError, KeyError, ValueError, UnicodeError) as exc:
            entry.update({"status": "failed", "error": str(exc)[:500]})
            run["items"].append({"source": source["id"], "status": "failed", "reason": str(exc)[:500]})
        else:
            pass
        manifest["next_source"] = None
        write_json(manifest_path, manifest)
    write_json(manifest_path, manifest)
    client.prune()
    run.update({"finished_at": now(), "requests": client.requests, "download_bytes": client.download_bytes,
                "cache_hits": client.hits})
    write_json(root / ".cache/last-run.json", run)
    return run
