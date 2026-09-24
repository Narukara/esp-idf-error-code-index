import unittest

from errindex.parser import Unresolved, analyze, evaluate


def records(text):
    return {x["symbol"]: x for x in analyze({"include/test.h": text}, "^ESP_ERR_")["definitions"]}


class ParserTests(unittest.TestCase):
    def test_nested_bases_and_decimal_offset(self):
        result = records("#define ESP_ERR_WIFI_BASE 0x3000\n#define ESP_ERR_RADIO_BASE (ESP_ERR_WIFI_BASE + 100)\n#define ESP_ERR_RADIO_BUSY (ESP_ERR_RADIO_BASE + 1)")
        self.assertEqual(result["ESP_ERR_RADIO_BUSY"]["value"], 0x3065)
        self.assertEqual(result["ESP_ERR_RADIO_BUSY"]["base_symbols"], ["ESP_ERR_RADIO_BASE", "ESP_ERR_WIFI_BASE"])

    def test_sparse_values_and_alias(self):
        result = records("#define ESP_ERR_X_BASE 0x1000\n#define ESP_ERR_X_A (ESP_ERR_X_BASE + 1)\n#define ESP_ERR_X_B (ESP_ERR_X_BASE + 16)\n#define ESP_ERR_X_OLD ESP_ERR_X_B")
        self.assertEqual(result["ESP_ERR_X_OLD"]["alias_of"], "ESP_ERR_X_B")
        self.assertEqual(result["ESP_ERR_X_B"]["value"], 0x1010)

    def test_config_default_not_assumed(self):
        result = analyze({"x.h": "#define ESP_ERR_X_BASE CONFIG_X_BASE\n#define ESP_ERR_X_BUSY (ESP_ERR_X_BASE + 3)",
                          "Kconfig": 'config X_BASE\n    hex "Base"\n    default 0x7000 if TARGET_X\n    default 0x8000\n'}, "^ESP_ERR_")
        busy = next(x for x in result["definitions"] if x["symbol"] == "ESP_ERR_X_BUSY")
        self.assertIsNone(busy["value"])
        self.assertTrue(busy["configurable"])
        self.assertIn("CONFIG_X_BASE", result["configuration"])

    def test_conditions_and_guards(self):
        result = analyze({"x.h": "#ifndef X_H\n#define X_H\n#if TARGET_A\n#define ESP_ERR_X 0x7001\n#else\n#define ESP_ERR_X 0x8001\n#endif\n#endif"}, "^ESP_ERR_")
        self.assertEqual(len(result["definitions"]), 2)
        self.assertTrue(all(x["resolution"] == "conditional" for x in result["definitions"]))
        self.assertNotIn("X_H", str([x["conditions"] for x in result["definitions"]]))

    def test_missing_cycle_and_ambiguous_never_guess(self):
        result = records("#define ESP_ERR_A ESP_ERR_B\n#define ESP_ERR_B ESP_ERR_A\n#define BASE 1\n#define BASE 2\n#define ESP_ERR_C (BASE+1)\n#define ESP_ERR_D (MISSING+1)")
        self.assertTrue(all(x["value"] is None for x in result.values()))

    def test_unknown_conditional_dependency(self):
        result = records("#if A\n#define BASE 1\n#else\n#define BASE 2\n#endif\n#define ESP_ERR_X (BASE+3)")
        self.assertIsNone(result["ESP_ERR_X"]["value"])

    def test_enum_increment_and_line_numbers(self):
        result = records("enum errors {\n ESP_ERR_A = 0x7001,\n ESP_ERR_B,\n ESP_ERR_C = (1 << 15)\n};")
        self.assertEqual(result["ESP_ERR_B"]["value"], 0x7002)
        self.assertEqual(result["ESP_ERR_B"]["line"], 3)

    def test_conditional_enum_not_guessed(self):
        result = analyze({"x.h": "enum errors {\n#if A\n ESP_ERR_A = 3,\n#endif\n ESP_ERR_B\n};"}, "^ESP_ERR_")
        self.assertEqual(result["definitions"], [])
        self.assertEqual(result["diagnostics"][0]["reason"], "enum_contains_preprocessor_directives")

    def test_stale_rule_is_reported(self):
        rule = {"symbol": "ESP_ERR_X", "file": "x.h", "expression": "7", "reason": "review", "evidence": "source"}
        result = analyze({"x.h": "#define ESP_ERR_X 8"}, "^ESP_ERR_", [rule])
        self.assertEqual(result["diagnostics"][0]["reason"], "unmatched_override")

    def test_no_eval_execution_and_bounds(self):
        for expression in ("__import__('os').system('echo unsafe')", "1 << 999999", "0xffffffffU", "-1 >> 1"):
            with self.assertRaises(Unresolved):
                evaluate(expression, lambda _: 0)

    def test_comments_continuations_and_integer_suffixes(self):
        result = records("/* ignore #define ESP_ERR_FAKE 1 */\n#define ESP_ERR_REAL \\\n (0x7000UL | 3) // trailing\n")
        self.assertEqual(set(result), {"ESP_ERR_REAL"})
        self.assertEqual(result["ESP_ERR_REAL"]["value"], 0x7003)
        self.assertEqual(result["ESP_ERR_REAL"]["line"], 2)

    def test_scope_specific_review(self):
        files = {"x.h": "#define ESP_ERR_END 7"}
        rule = {"symbol": "ESP_ERR_END", "file": "x.h", "expression": "7", "role": "error", "reason": "Upstream returns it", "evidence": "https://example.com"}
        result = analyze(files, "^ESP_ERR_", [rule])
        self.assertEqual(result["definitions"][0]["role"], "error")
        self.assertEqual(analyze({"x.h": "#define ESP_ERR_END 8"}, "^ESP_ERR_", [rule])["definitions"][0]["role"], "marker")


if __name__ == "__main__":
    unittest.main()
