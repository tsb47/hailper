"""Unit tests for the parts of HaiLPER that do not need LibreOffice/UNO.

Run with:  python3 -m unittest discover -s tests -v
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "copilot"))

import cp_config  # noqa: E402
import cp_format  # noqa: E402
import cp_prompts  # noqa: E402
import cp_providers  # noqa: E402


class TestDirectives(unittest.TestCase):
    def test_format_dict(self):
        self.assertEqual(
            cp_prompts.parse_directive('{"format": {"bold": true}}'),
            ("format", [{"bold": True}]))

    def test_format_list(self):
        parsed = cp_prompts.parse_directive(
            '```json\n{"format": [{"align": "center"}, {"para_style": "X"}]}\n```')
        self.assertEqual(parsed[0], "format")
        self.assertEqual(len(parsed[1]), 2)
        self.assertEqual(parsed[1][0]["align"], "center")

    def test_format_in_prose(self):
        parsed = cp_prompts.parse_directive(
            'Sure: {"format":[{"find":"foo","underline":true}]} done')
        self.assertEqual(parsed[0], "format")
        self.assertEqual(parsed[1][0]["find"], "foo")

    def test_edit(self):
        parsed = cp_prompts.parse_directive(
            '{"edit": {"action": "insert", "text": "hi"}}')
        self.assertEqual(parsed[0], "edit")
        self.assertEqual(parsed[1]["text"], "hi")

    def test_document(self):
        self.assertEqual(cp_prompts.parse_directive('{"request": "document"}'),
                         ("document", None))

    def test_none(self):
        self.assertIsNone(cp_prompts.parse_directive("just some prose"))


class TestSuggestions(unittest.TestCase):
    def test_parse(self):
        found = cp_prompts.parse_suggestions(
            '{"suggestions":[{"original":"teh","replacement":"the",'
            '"reason":"typo"}]}')
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["replacement"], "the")


class TestConfig(unittest.TestCase):
    def test_deep_merge(self):
        base = {"a": {"b": 1, "c": 2}, "d": 3}
        merged = cp_config._deep_merge(base, {"a": {"b": 9}})
        self.assertEqual(merged["a"]["b"], 9)
        self.assertEqual(merged["a"]["c"], 2)
        self.assertEqual(merged["d"], 3)

    def test_defaults_present(self):
        for key in ("allow_edits", "allow_document_access", "allow_formatting",
                    "track_changes", "remember_keys", "stream", "providers"):
            self.assertIn(key, cp_config.DEFAULTS)


class TestProviders(unittest.TestCase):
    def test_many_presets(self):
        self.assertGreaterEqual(len(cp_providers.provider_ids()), 50)

    def test_specs_complete(self):
        valid = ("openai", "azure", "anthropic", "gemini", "ollama")
        for pid, spec in cp_providers.PROVIDERS.items():
            for key in ("label", "protocol", "base_url", "default_model",
                        "requires_key", "models"):
                self.assertIn(key, spec, pid)
            self.assertIn(spec["protocol"], valid, pid)

    def test_custom_provider(self):
        self.assertIn("custom", cp_providers.PROVIDERS)


class TestFormatHelpers(unittest.TestCase):
    def test_requires_confirmation(self):
        self.assertFalse(cp_format.requires_confirmation([{"bold": True}]))
        self.assertFalse(cp_format.requires_confirmation(
            [{"insert_table": {"rows": 2, "cols": 2}}]))
        self.assertTrue(cp_format.requires_confirmation(
            [{"target": "document", "bold": True}]))
        self.assertTrue(cp_format.requires_confirmation(
            [{"page_margins": {"top": 2}}]))
        self.assertTrue(cp_format.requires_confirmation([{"landscape": True}]))

    def test_char_props(self):
        props = cp_format._char_props(
            {"bold": True, "underline": "double", "color": "#FF0000"})
        self.assertEqual(props["CharWeight"], 150.0)
        self.assertEqual(props["CharUnderline"], 2)
        self.assertEqual(props["CharColor"], 0xFF0000)

    def test_para_props(self):
        props = cp_format._para_props(
            {"align": "center", "space_before": 0.5, "indent_left": 1.0})
        self.assertEqual(props["ParaAdjust"], 3)
        self.assertEqual(props["ParaTopMargin"], 500)
        self.assertEqual(props["ParaLeftMargin"], 1000)

    def test_helpers(self):
        self.assertEqual(cp_format._rgb("#00FF00"), 0x00FF00)
        self.assertEqual(cp_format._cm(2.5), 2500)
        self.assertIsNone(cp_format._cm("nonsense"))


if __name__ == "__main__":
    unittest.main()
