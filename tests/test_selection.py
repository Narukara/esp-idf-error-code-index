import unittest
import io
import zipfile
from errindex.selection import select_files
from errindex.sources import read_archive


class SelectionTests(unittest.TestCase):
    def select(self, files, mode):
        reads = []
        def read(path):
            reads.append(path)
            return files[path]
        result, evidence = select_files(files, read, mode)
        return result, evidence, reads

    def test_default_headers_never_read_implementation(self):
        files = {"CMakeLists.txt": 'idf_component_register(SRCS "x.c" INCLUDE_DIRS "include")',
                 "include/x.h": "", "private/x.h": "", "x.c": ""}
        result, evidence, reads = self.select(files, "headers")
        self.assertNotIn("x.c", reads)
        self.assertIn("private/x.h", result)
        self.assertEqual(evidence["skipped_files"], 1)

    def test_public_headers_and_transitive_local_includes(self):
        files = {"CMakeLists.txt": 'idf_component_register(INCLUDE_DIRS "include" PRIV_INCLUDE_DIRS "private")',
                 "include/api.h": '#include "../private/base.h"', "private/base.h": '#include "deeper.h"',
                 "private/deeper.h": "", "private/unused.h": "", "x.c": ""}
        result, evidence, reads = self.select(files, "public-headers")
        self.assertEqual(set(result), {"CMakeLists.txt", "include/api.h", "private/base.h", "private/deeper.h"})
        self.assertEqual(evidence["public_header_candidates"], ["include/api.h"])

    def test_dynamic_cmake_falls_back_to_all_headers(self):
        files = {"CMakeLists.txt": 'idf_component_register(INCLUDE_DIRS ${public_dirs})', "x.h": "", "x.c": ""}
        result, evidence, _ = self.select(files, "public-headers")
        self.assertIn("x.h", result)
        self.assertIn("fallback_all_headers", evidence["reasons"])
        self.assertNotIn("x.c", result)

    def test_explicit_registered_header_outside_public_root(self):
        files = {"CMakeLists.txt": 'idf_component_register(INCLUDE_DIRS include)\nidf_define_esp_err_codes(HEADERS private/errors.h)',
                 "include/api.h": "", "private/errors.h": "", "private/unused.h": ""}
        result, _, _ = self.select(files, "public-headers")
        self.assertIn("private/errors.h", result)
        self.assertNotIn("private/unused.h", result)

    def test_ambiguous_include_keeps_all_matches(self):
        files = {"CMakeLists.txt": 'idf_component_register(INCLUDE_DIRS include)', "include/api.h": '#include <base.h>',
                 "a/base.h": "", "b/base.h": ""}
        result, _, _ = self.select(files, "public-headers")
        self.assertIn("a/base.h", result)
        self.assertIn("b/base.h", result)

    def test_missing_cmake_and_dynamic_include_are_explicit_fallbacks(self):
        _, evidence, _ = self.select({"x.h":""}, "public-headers")
        self.assertIn("fallback_all_headers", evidence["reasons"])
        result, evidence, _ = self.select({"CMakeLists.txt": "idf_component_register(INCLUDE_DIRS include)",
                                          "include/a.h": "#include GENERATED_HEADER", "private/b.h": ""}, "public-headers")
        self.assertIn("private/b.h", result)
        self.assertIn("dynamic_header_include", evidence["reasons"])

    def test_full_mode_reads_implementation(self):
        result, _, _ = self.select({"x.h":"", "x.c":""}, "full")
        self.assertEqual(len(result), 2)

    def test_zip_does_not_decompress_unselected_oversized_implementation(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("include/api.h", "#define ESP_ERR_X 1")
            archive.writestr("huge.c", "x" * 10000)
        files, evidence = read_archive(buffer.getvalue(), {"max_file_bytes": 100, "max_source_bytes": 1000, "max_files": 10}, "headers", True)
        self.assertEqual(list(files), ["include/api.h"])
        self.assertEqual(evidence["skipped_files"], 1)
