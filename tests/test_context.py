import hashlib
import unittest
from types import SimpleNamespace

from errindex.network import SourceError
from errindex.parser import analyze
from errindex.sources import download_source


class ContextTests(unittest.TestCase):
    def test_context_resolves_without_claiming_dependency_definitions(self):
        files = {"shared.h": "#define ESP_ERR_SHARED_BASE 0x3000",
                 "api.h": "#define ESP_ERR_BUSY (ESP_ERR_SHARED_BASE + 1)"}
        result = analyze(files, "^ESP_ERR_", context_headers=["shared.h"])
        self.assertEqual(len(result["definitions"]), 1)
        record = result["definitions"][0]
        self.assertEqual(record["value"], 0x3001)
        self.assertEqual(record["context_references"][0]["file"], "shared.h")
        self.assertEqual(record["context_references"][0]["line"], 1)

    def test_context_does_not_override_ambiguous_or_configurable_definitions(self):
        for shared in ("#define ESP_ERR_BASE CONFIG_BASE", "#define ESP_ERR_BASE 0x3000\n#define ESP_ERR_BASE 0x4000"):
            result = analyze({"shared.h": shared, "api.h": "#define ESP_ERR_BUSY (ESP_ERR_BASE + 1)"},
                             "^ESP_ERR_", context_headers=["shared.h"])
            self.assertIsNone(result["definitions"][0]["value"])

    def client(self):
        bodies = {"demo/api.h": b"#define ESP_ERR_BUSY (ESP_ERR_BASE + 1)",
                  "shared/base.h": b"#define ESP_ERR_BASE 0x3000"}
        def blob(path):
            body = bodies[path]
            return {"path": path.split("/")[-1], "type": "blob", "size": len(body), "mode": "100644",
                    "sha": hashlib.sha1(f"blob {len(body)}\0".encode() + body).hexdigest()}
        trees = {"root": [{"path": "demo", "type": "tree", "sha": "demo-tree"},
                          {"path": "shared", "type": "tree", "sha": "shared-tree"}],
                 "demo-tree?recursive=1": [blob("demo/api.h"), {"path": "lib", "type": "commit", "sha": "pinned-lib"}],
                 "shared-tree": [blob("shared/base.h")]}
        reads = []
        def get(url, **kwargs):
            self.assertIn("/fixed-commit/", url)
            path = url.split("/fixed-commit/")[1]
            reads.append(path)
            return bodies[path]
        client = SimpleNamespace(limits={"max_file_bytes": 1024, "max_files": 10, "max_source_bytes": 2048},
                                 check_time=lambda: None, get=get,
                                 json=lambda url, **kw: {"tree": trees[url.split("/git/trees/")[1]]})
        return client, reads

    def test_only_explicit_submodule_is_excluded_and_context_is_commit_pinned(self):
        client, reads = self.client()
        source = {"kind": "github", "repository": "vendor/repo", "path": "demo", "scan_mode": "headers"}
        identity = {"root_tree": "root", "commit": "fixed-commit"}
        for exclusions in ([], ["another-lib"]):
            with self.assertRaises(SourceError):
                download_source({**source, "exclude_submodules": exclusions}, identity, client)
        self.assertEqual(reads, [])
        files, evidence = download_source({**source, "exclude_submodules": ["lib"],
                                          "context_headers": ["shared/base.h"]}, identity, client)
        self.assertEqual(set(files), {"demo/api.h", "shared/base.h"})
        self.assertEqual(reads, ["demo/api.h", "shared/base.h"])
        self.assertEqual(evidence["excluded_submodules"], [{"path": "lib", "commit": "pinned-lib"}])
        self.assertEqual(evidence["context_headers"], ["shared/base.h"])
        self.assertEqual(evidence["selection"]["selected_files"], 1)
