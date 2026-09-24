"""Merge only validated data from the dedicated pending bot branch; never execute its code."""
import json
import re
import subprocess

from .storage import read_json, write_json


def resume(root, ref):
    if ref != "refs/remotes/origin/automation/observations":
        raise ValueError("Only the dedicated automation branch can supply pending data")
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=root, timeout=30)
    paths = git("ls-tree", "-r", "--name-only", ref, "--", "data/").decode().splitlines()
    selected = [x for x in paths if re.fullmatch(r"data/components/[a-f0-9]{64}\.json", x)]
    if len(selected) > 10000:
        raise ValueError("Too many pending results; inspect the automation branch")
    pending = json.loads(git("show", ref + ":data/manifest.json"))
    manifest = read_json(root / "data/manifest.json", {"schema_version": 1, "sources": {}})
    total = 0
    for path in selected:
        if (root / path).exists():
            continue
        size = int(git("cat-file", "-s", ref + ":" + path))
        total += size
        if size > 4 * 1024 * 1024 or total > 50 * 1024 * 1024:
            raise ValueError("Pending data exceeds merge budget")
        result = json.loads(git("show", ref + ":" + path))
        if result.get("schema_version") != 1 or result.get("fingerprint") != path.split("/")[-1][:-5]:
            raise ValueError("Invalid pending evidence")
        write_json(root / path, result)
    for source, entry in pending["sources"].items():
        current = manifest["sources"].get(source, {})
        if entry.get("accepted_at", "") >= current.get("accepted_at", ""):
            manifest["sources"][source] = entry
    manifest["next_source"] = pending.get("next_source")
    write_json(root / "data/manifest.json", manifest)
