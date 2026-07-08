import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penguin_app", ROOT / "app.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ContextFlowTests(unittest.TestCase):
    def test_report_command_output_records_execution_and_keeps_history_conversation_only(self):
        api = module.Api()
        api.chat_history = [{"role": "user", "content": "hello"}]

        result = api.report_command_output("echo hi", "hi", True)

        self.assertEqual(result["status"], "reported")
        self.assertIn("echo hi", result["next_prompt"])
        self.assertEqual(api.chat_history, [{"role": "user", "content": "hello"}])
        self.assertEqual(api.investigating_obj["executed_commands"][-1]["command"], "echo hi")

    def test_build_messages_include_state_and_investigation_context(self):
        api = module.Api()
        api.state = "understand"
        api.investigating_obj = {
            "issue": "network issue",
            "summary": "The interface is down",
            "status": "active",
        }
        api.chat_history = [{"role": "user", "content": "hello"}]

        messages = api.build_messages("What next?")

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("understand", messages[0]["content"])
        self.assertIn("network issue", messages[2]["content"])
        self.assertEqual(messages[-1]["content"], "What next?")


if __name__ == "__main__":
    unittest.main()
