import copy
import io
import tempfile
import unittest
import subprocess
import zipfile
import shutil
from pathlib import Path
from unittest.mock import patch

from errindex.engine import scan
from errindex.network import BudgetExceeded, Client, SourceError
from errindex.report import report, build
from errindex.sources import read_archive
from errindex.storage import read_json, write_json
from errindex.resume import resume

CONFIG = read_json(Path(__file__).parents[1] / "config/sources.json")
IDENTITY = {"kind": "github", "version": "v5.5.1", "commit": "a" * 40,
            "component_url": "https://github.com/espressif/esp-idf", "repository_url": "https://github.com/espressif/esp-idf"}


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = copy.deepcopy(CONFIG)
        self.config["sources"] = self.config["sources"][:1]
        write_json(self.root / "config/sources.json", self.config)
        self.rules = {"schema_version": 1, "rules": []}

    def first_scan(self, files=None):
        with patch("errindex.engine.inspect_source", return_value=IDENTITY), patch("errindex.engine.download_source", return_value=(files or {"x.h": "#define ESP_ERR_X 0x7001"}, {})):
            return scan(self.root, self.config, self.rules)

    def test_incremental_survives_no_cache_and_no_changes(self):
        self.first_scan()
        before = (self.root / "data/manifest.json").read_bytes()
        with patch("errindex.engine.inspect_source", return_value=IDENTITY), patch("errindex.engine.download_source", side_effect=AssertionError("Do not download again")):
            result = scan(self.root, self.config, self.rules)
        self.assertEqual(result["items"][0]["status"], "reused")
        self.assertEqual(before, (self.root / "data/manifest.json").read_bytes())

    def test_failure_retains_previous_result(self):
        self.first_scan()
        with patch("errindex.engine.inspect_source", side_effect=SourceError("Unavailable")):
            scan(self.root, self.config, self.rules)
        entry = read_json(self.root / "data/manifest.json")["sources"]["idf/esp_common"]
        self.assertEqual(entry["status"], "failed")
        self.assertTrue((self.root / entry["result"]).exists())
        self.assertTrue(report(self.root)["definitions"][0]["stale"])

    def test_budget_preserves_pending_source(self):
        with patch("errindex.engine.inspect_source", side_effect=BudgetExceeded("Request budget")):
            result = scan(self.root, self.config, self.rules)
        self.assertTrue(result["budget_exhausted"])
        self.assertEqual(read_json(self.root / "data/manifest.json")["next_source"], "idf/esp_common")

    def test_parser_upgrade_invalidates_existing_result(self):
        self.first_scan()
        with patch("errindex.engine.PARSER_VERSION", "future-test-version"), patch("errindex.engine.inspect_source", return_value=IDENTITY), patch("errindex.engine.download_source", return_value=({"x.h": "#define ESP_ERR_X 0x7001"}, {})) as download:
            scan(self.root, self.config, self.rules)
        download.assert_called_once()
        self.assertEqual(len(list((self.root / "data/components").glob("*.json"))), 2)

    def test_new_revision_preserves_history(self):
        self.first_scan()
        newer = {**IDENTITY, "commit": "b" * 40}
        with patch("errindex.engine.inspect_source", return_value=newer), patch("errindex.engine.download_source", return_value=({"x.h": "#define ESP_ERR_X 0x7002"}, {})):
            scan(self.root, self.config, self.rules)
        self.assertEqual(len(list((self.root / "data/components").glob("*.json"))), 2)
        self.assertEqual(report(self.root)["definitions"][0]["value"], 0x7002)

    def test_force_changed_content_keeps_both_observations(self):
        self.first_scan()
        with patch("errindex.engine.inspect_source", return_value=IDENTITY), patch("errindex.engine.download_source", return_value=({"x.h": "#define ESP_ERR_X 0x7002"}, {})):
            scan(self.root, self.config, self.rules, force=True)
        self.assertEqual(len(list((self.root / "data/components").glob("*.json"))), 2)
        self.assertEqual(report(self.root)["definitions"][0]["value"], 0x7002)

    def test_report_no_base_alias_or_sparse_envelope_conflicts(self):
        self.first_scan({"x.h": "#define ESP_ERR_X_BASE 0x7000\n#define ESP_ERR_A 0x7001\n#define ESP_ERR_B 0x7010\n#define ESP_ERR_OLD ESP_ERR_A"})
        result = report(self.root)
        self.assertEqual(result["components"][0]["values"], [0x7001, 0x7010])
        self.assertEqual(result["overlaps"], [])

    def test_numeric_overlap_retains_conditions(self):
        self.first_scan({"x.h": "#define ESP_ERR_A 0x7001\n#if TARGET_A\n#define ESP_ERR_B 0x7001\n#endif"})
        self.assertEqual(report(self.root)["overlaps"][0]["classification"], "conditional-overlap")

    def test_low_component_budget_advances_queue(self):
        self.config["sources"] = CONFIG["sources"][:2]
        self.config["limits"]["max_components"] = 1
        self.first_scan()
        self.assertEqual(read_json(self.root / "data/manifest.json")["next_source"], "idf/nvs_flash")

    def test_build_versions_scripts_and_index_to_avoid_mixed_cached_assets(self):
        self.first_scan()
        shutil.copytree(Path(__file__).parents[1] / "web", self.root / "web")
        output = self.root / "site"
        build(self.root, output)
        before = (output / "index.html").read_text(encoding="utf-8")
        self.assertRegex(before, r'data-index-url="index.json\?v=[a-f0-9]{16}"')
        self.assertRegex(before, r'src="i18n.js\?v=[a-f0-9]{16}"')
        self.assertTrue((output / "i18n.js").exists())
        build(self.root, output)
        self.assertEqual(before, (output / "index.html").read_text(encoding="utf-8"))
        with (self.root / "web/app.js").open("a", encoding="utf-8") as stream:
            stream.write("\n// Changed script\n")
        build(self.root, output)
        self.assertNotEqual(before, (output / "index.html").read_text(encoding="utf-8"))

    def test_cache_offline_miss_never_opens_network(self):
        client = Client(self.root / "cache", CONFIG["limits"], offline=True)
        with patch.object(client.opener, "open", side_effect=AssertionError("Offline")):
            with self.assertRaises(SourceError):
                client.get("https://api.github.com/example")

    def test_request_budget_before_network(self):
        client = Client(self.root / "cache", CONFIG["limits"])
        client.requests = CONFIG["limits"]["max_requests"]
        with self.assertRaises(BudgetExceeded):
            client.get("https://api.github.com/example")

    def test_remaining_download_budget_defers_instead_of_failure(self):
        limits = {**CONFIG["limits"], "max_download_bytes": 10}
        client = Client(self.root / "cache", limits)
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = response
        response.headers = {"Content-Length": "20"}
        with patch.object(client.opener, "open", return_value=response):
            with self.assertRaises(BudgetExceeded):
                client.get("https://api.github.com/example")
        response.read.assert_not_called()

    def test_pending_branch_restores_progress_without_running_its_code(self):
        def git(*args):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        git("init", "-b", "main")
        git("config", "user.name", "Test")
        git("config", "user.email", "test@example.invalid")
        write_json(self.root / "data/manifest.json", {"schema_version": 1, "sources": {}})
        git("add", "config", "data")
        git("commit", "-m", "Baseline")
        git("checkout", "-b", "automation/observations")
        self.first_scan()
        git("add", "data")
        git("commit", "-m", "Pending observation")
        git("update-ref", "refs/remotes/origin/automation/observations", "HEAD")
        git("checkout", "main")
        self.assertFalse(read_json(self.root / "data/manifest.json")["sources"])
        resume(self.root, "refs/remotes/origin/automation/observations")
        self.assertIn("idf/esp_common", read_json(self.root / "data/manifest.json")["sources"])
        with patch("errindex.engine.inspect_source", return_value=IDENTITY), patch("errindex.engine.download_source", side_effect=AssertionError("Must reuse proposed result")):
            result = scan(self.root, self.config, self.rules)
        self.assertEqual(result["items"][0]["status"], "reused")

    def test_private_hosts_refused(self):
        client = Client(self.root / "cache", CONFIG["limits"])
        for url in ("http://localhost/test", "https://127.0.0.1/x", "https://api.github.com@evil.example/x"):
            with self.assertRaises(SourceError):
                client.get(url)

    def test_zip_traversal_and_size_limits(self):
        for path, body in (("../outside.h", "x"), ("x.h", "x" * 100)):
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, "w") as output:
                output.writestr(path, body)
            limits = {**CONFIG["limits"], "max_file_bytes": 50}
            with self.assertRaises(SourceError):
                read_archive(archive.getvalue(), limits)

    def test_zip_excludes_tests_and_examples(self):
        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("include/x.h", "#define ESP_ERR_X 1")
            output.writestr("examples/x.h", "#define ESP_ERR_FAKE 2")
        self.assertEqual(list(read_archive(archive.getvalue(), CONFIG["limits"])), ["include/x.h"])


if __name__ == "__main__":
    unittest.main()
