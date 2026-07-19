import importlib.util
import sqlite3
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from session_manager import SessionManager

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("penguin_app", ROOT / "app.py")
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ContextFlowTests(unittest.TestCase):
    def test_duplicate_commands_are_only_blocked_when_run_back_to_back(self):
        api = module.Api()

        api._record_command("echo hi", True, "first")
        self.assertFalse(api._should_run_command("echo hi"))

        api._record_command("echo something-else", True, "second")
        self.assertTrue(api._should_run_command("echo hi"))

    def test_sqlite_db_store_round_trip(self):
        store_path = ROOT / "sessions.db"
        if store_path.exists():
            store_path.unlink()

        manager = SessionManager(store_path)
        created = manager.create_session({
            "id": "db-only-session",
            "title": "db-only chat",
            "chatHistory": [{"role": "user", "content": "hello"}],
            "investigation": {"issue": "db only"},
            "isContinue": False,
        })

        with sqlite3.connect(store_path) as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
            ).fetchall()

        self.assertTrue(rows)
        self.assertEqual(created["title"], "db-only chat")
        self.assertEqual(manager.load_session(created["id"])["title"], "db-only chat")

    def test_run_command_records_execution_and_keeps_history_conversation_only(self):
        api = module.Api()
        api.chat_history = [{"role": "user", "content": "hello"}]

        result = api.run_command("echo hi")
        prompt = api.report_command_output("echo hi", result["output"], result["success"])

        self.assertTrue(result["success"])
        self.assertEqual(prompt["status"], "reported")
        self.assertIn("echo hi", prompt["next_prompt"])
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

    def test_session_snapshot_is_saved_and_restored(self):
        api = module.Api()
        api.chat_history = [{"role": "user", "content": "hello"}]
        api.investigating_obj = {"issue": "network issue", "summary": "The interface is down"}
        api.continue_event = True

        saved = api.save_current_session()
        self.assertIsInstance(saved["session_id"], str)

        refreshed = api.create_new_session()
        self.assertEqual(api.chat_history, [])
        self.assertEqual(api.investigating_obj["issue"], "")
        self.assertFalse(api.continue_event)

        restored = api.open_session(saved["session_id"])
        self.assertEqual(restored["chat_history"][0]["content"], "hello")
        self.assertEqual(restored["investigating_obj"]["issue"], "network issue")
        self.assertTrue(restored["continue_event"])

    def test_sessions_list_returns_previous_sessions(self):
        api = module.Api()
        api.chat_history = [{"role": "user", "content": "persist me"}]
        api.investigating_obj = {"issue": "persistent issue", "summary": "still active"}
        api.save_current_session()

        sessions = api.list_sessions()
        self.assertTrue(any(session["title"] for session in sessions))

    @patch("subprocess.run")
    def test_model_selector_lists_installed_ollama_models(self, mock_run):
        mock_run.return_value = subprocess.CompletedProcess(
            args=["ollama", "list"],
            returncode=0,
            stdout="NAME\tSIZE\tMODIFIED\nqwen2.5-coder:3b\t1.2 GB\t2026-07-19\nllama3.2:3b\t1.1 GB\t2026-07-19\n",
            stderr="",
        )

        api = module.Api()
        models = api.list_models()

        self.assertIn("qwen2.5-coder:3b", models)
        self.assertIn("llama3.2:3b", models)

    def test_assistant_json_is_saved_without_flattening_or_reconstruction(self):
        api = module.Api()
        assistant_payload = {
            "reply": "Python is missing.",
            "decision": "diagnose",
            "steps": [{"type": "command", "command": "python3 --version"}],
            "investigation_update": {"summary": "Checking Python"},
        }
        api.chat_history = [{"role": "user", "content": "hello"}, {"role": "assistant", **assistant_payload}]
        api.investigating_obj = {"issue": "python missing"}

        session_id = api.save_current_session()["session_id"]
        restored = api.open_session(session_id)

        self.assertEqual(restored["chat_history"][-1]["reply"], "Python is missing.")
        self.assertEqual(restored["chat_history"][-1]["steps"][0]["command"], "python3 --version")
        self.assertEqual(restored["investigating_obj"]["issue"], "python missing")

    def test_delete_session_removes_saved_chat(self):
        api = module.Api()
        api.chat_history = [{"role": "user", "content": "delete me"}]
        api.investigating_obj = {"issue": "temporary"}
        saved = api.save_current_session()

        before = len(api.list_sessions())
        result = api.delete_session(saved["session_id"])

        self.assertEqual(result["status"], "deleted")
        self.assertEqual(len(api.list_sessions()), before - 1)

    def test_controller_prompt_is_not_saved_as_a_user_message(self):
        api = module.Api()
        controller_prompt = """
The requested command has finished.

Status: succeeded

Command:
echo hi

Output:
hi

Do NOT repeat this command unless the result has changed.
Choose the next diagnostic step based on the above output.
"""

        with patch("api.chat") as mock_chat:
            mock_chat.return_value = {
                "message": {
                    "content": '{"reply": "Checking next step.", "decision": "diagnose", "steps": [], "investigation_update": {}}'
                }
            }
            api.respond(controller_prompt)

        self.assertEqual(len(api.chat_history), 1)
        self.assertEqual(api.chat_history[0]["role"], "assistant")

    def test_internal_investigation_json_is_not_saved_as_user_message(self):
        api = module.Api()
        internal_prompt = '{"issue": "python missing", "summary": "Checking Python", "status": "active", "facts": {}, "hypotheses": [], "executed_commands": [], "questions_asked": [], "pending_questions": [], "root_cause": null, "solution": null, "confidence": 0, "next_goal": ""}'

        with patch("api.chat") as mock_chat:
            mock_chat.return_value = {
                "message": {
                    "content": '{"reply": "Checking next step.", "decision": "diagnose", "steps": [], "investigation_update": {}}'
                }
            }
            api.respond(internal_prompt)

        self.assertEqual(len(api.chat_history), 1)
        self.assertEqual(api.chat_history[0]["role"], "assistant")


if __name__ == "__main__":
    unittest.main()
