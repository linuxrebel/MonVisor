"""
tests/test_smoke.py
Minimal smoke tests: packaging self-containment + CLI wiring.

Uses stdlib unittest (no extra deps), so it runs with either:
    python -m unittest discover -s tests
    pytest                      # if installed

Deliberately imports only light modules (config, cli.main, schema, recommend)
to avoid pulling chromadb/ollama at collection time.
"""

import json
import unittest

from click.testing import CliRunner

from monvisor import config


class TestBundledKnowledge(unittest.TestCase):
    def test_corpus_resolves_into_package(self):
        self.assertTrue(config.CORPUS_SOURCE.exists(),
                        f"corpus missing: {config.CORPUS_SOURCE}")
        # Default (no env override) must resolve to the bundled copy.
        self.assertIn("monvisor/knowledge", str(config.CORPUS_SOURCE))

    def test_exemplars_present_and_nonempty(self):
        self.assertTrue(config.EXEMPLARS_SOURCE.exists())
        files = list(config.EXEMPLARS_SOURCE.rglob("*"))
        self.assertTrue(any(f.is_file() for f in files), "no exemplar files bundled")

    def test_corpus_is_valid_jsonl(self):
        with open(config.CORPUS_SOURCE, encoding="utf-8") as f:
            lines = [ln for ln in f if ln.strip()]
        self.assertGreater(len(lines), 50, "corpus suspiciously small")
        first = json.loads(lines[0])
        for key in ("instruction", "output"):
            self.assertIn(key, first)


class TestCliWiring(unittest.TestCase):
    def setUp(self):
        from monvisor.cli.main import cli
        self.cli = cli
        self.runner = CliRunner()

    def test_help_runs(self):
        result = self.runner.invoke(self.cli, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("MonVisor", result.output)

    def test_version(self):
        result = self.runner.invoke(self.cli, ["--version"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("0.1.0", result.output)

    def test_expected_commands_registered(self):
        for name in ("init", "scan", "review", "generate", "ui",
                     "deploy", "nginx", "env", "config", "knowledge", "ask"):
            self.assertIn(name, self.cli.commands, f"missing command: {name}")

    def test_ask_help_runs(self):
        result = self.runner.invoke(self.cli, ["ask", "--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("knowledge base", result.output)

    def test_ask_fallback_message_well_formed(self):
        from monvisor.cli import main
        # Fallback must decline clearly and point to the issue tracker.
        self.assertIn("not yet learned", main._ASK_FALLBACK.lower())
        self.assertIn("github.com/linuxrebel/MonVisor/issues", main._ASK_FALLBACK)
        # Distance gate sits between in-domain (~0.3) and out-of-domain (~0.46).
        self.assertGreater(main._ASK_MAX_DISTANCE, 0.30)
        self.assertLess(main._ASK_MAX_DISTANCE, 0.46)


class TestConfigSanity(unittest.TestCase):
    def test_fingerprints_well_formed(self):
        self.assertGreater(len(config.FINGERPRINTS), 10)
        for port, stype in config.FINGERPRINTS.items():
            self.assertIsInstance(port, int)
            self.assertIsInstance(stype, str)
            self.assertTrue(stype)

    def test_all_ports_string_builds(self):
        self.assertIn("9090", config.ALL_PORTS)


class TestSchema(unittest.TestCase):
    def test_schema_defines_core_tables(self):
        from monvisor.db.schema import SCHEMA
        for table in ("environments", "cidrs", "discoveries", "services",
                      "configs", "dashboards", "sessions", "settings"):
            self.assertIn(table, SCHEMA, f"schema missing table: {table}")


class TestRecommend(unittest.TestCase):
    def test_missing_exporter_recommended(self):
        from monvisor.recommend import recommendations
        svcs = [{"host": "db1", "service_type": "mysql", "port": 3306}]
        recs = recommendations(svcs)
        self.assertIn("db1", recs)
        self.assertIn("mysqld_exporter", recs["db1"])
        # node_exporter always recommended when absent on the host.
        self.assertIn("node_exporter", recs["db1"])

    def test_fully_instrumented_host_omitted(self):
        from monvisor.recommend import recommendations
        svcs = [{"host": "h1", "service_type": "node_exporter", "port": 9100}]
        self.assertNotIn("h1", recommendations(svcs))


if __name__ == "__main__":
    unittest.main()
