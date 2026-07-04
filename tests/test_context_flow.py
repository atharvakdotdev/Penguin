import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penguin_app", ROOT / "app.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ContextFlowTests(unittest.TestCase):
    def test_report_command_output_returns_context_without_persisted_history(self):
        api = module.Api()

        result = api.report_command_output("echo hi", "hi", True)

        self.assertEqual(result["status"], "reported")
        self.assertIn("echo hi", result["next_prompt"])
        self.assertNotIn("chat_history", api.__dict__)
        self.assertNotIn("last_context_report", api.__dict__)


if __name__ == "__main__":
    unittest.main()
