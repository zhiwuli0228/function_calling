import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.function_calling.logx.cli import main
from src.function_calling.logx.llm import build_log_analysis_messages, config_from_env


class AnalyzeTests(TestCase):
    def test_build_messages(self) -> None:
        messages = build_log_analysis_messages("what happened", ["a:1:ERROR failed", "a:2:timeout"])
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("what happened", messages[1]["content"])
        self.assertIn("ERROR failed", messages[1]["content"])

    def test_config_from_env_explicit(self) -> None:
        cfg = config_from_env(base_url="https://api.openai.com/", api_key="k", model="gpt-4o-mini", timeout=10)
        self.assertEqual(cfg.base_url, "https://api.openai.com")
        self.assertEqual(cfg.api_key, "k")
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertEqual(cfg.timeout, 10)

    def test_cli_analyze(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "collect.log").write_text("ok\nERROR request timeout\n", encoding="utf-8")

            with patch("src.function_calling.logx.cli.chat_completion", return_value="analysis done") as mocked:
                code = main(
                    [
                        "analyze",
                        "请分析问题",
                        str(root),
                        "--name",
                        "collect*",
                        "--pattern",
                        "ERROR|timeout",
                        "--llm-api-key",
                        "test-key",
                        "--llm-model",
                        "gpt-4o-mini",
                        "--llm-base-url",
                        "https://api.openai.com",
                        "--max-lines",
                        "10",
                    ]
                )
                self.assertEqual(code, 0)
                self.assertEqual(mocked.call_count, 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
