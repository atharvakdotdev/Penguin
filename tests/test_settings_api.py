import unittest

from api import Api


class SettingsApiTests(unittest.TestCase):
    def test_save_settings_updates_model_and_auto_allow(self):
        api = Api()
        api.model = "old-model"
        api.auto_allow = False

        result = api.save_settings(
            {"default_model": "new-model", "permission_mode": "auto_confirm"}
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(api.default_model, "new-model")
        self.assertEqual(api.model, "new-model")
        self.assertTrue(api.auto_allow)

    def test_get_settings_returns_current_state(self):
        api = Api()
        api.default_model = "custom-model"
        api.current_chat_model = "custom-model"
        api.auto_allow = True

        settings = api.get_settings()

        self.assertEqual(settings["default_model"], "custom-model")
        self.assertEqual(settings["current_chat_model"], "custom-model")
        self.assertEqual(settings["permission_mode"], "auto_confirm")

    def test_save_settings_persists_default_model_and_permission(self):
        api = Api()
        result = api.save_settings(
            {"default_model": "session-model", "permission_mode": "auto_confirm"}
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(api.default_model, "session-model")
        self.assertEqual(api.current_chat_model, "session-model")
        self.assertTrue(api.auto_allow)

        restored = Api()
        self.assertEqual(restored.default_model, "session-model")
        self.assertEqual(restored.model, "session-model")
        self.assertTrue(restored.auto_allow)

    def test_set_model_is_locked_after_chat_started(self):
        api = Api()
        api.chat_started = True
        api.current_chat_model = "old-model"

        response = api.set_model("new-model")

        self.assertEqual(response["status"], "error")
        self.assertEqual(response["model"], "old-model")
        self.assertEqual(api.current_chat_model, "old-model")

    def test_create_new_session_resets_to_default_model(self):
        api = Api()
        api.default_model = "default-model"
        api.current_chat_model = "custom-model"
        api.chat_started = True

        result = api.create_new_session()

        self.assertEqual(result["status"], "created")
        self.assertEqual(api.current_chat_model, "default-model")
        self.assertFalse(api.chat_started)
        self.assertEqual(result["default_model"], "default-model")
        self.assertEqual(result["current_chat_model"], "default-model")


if __name__ == "__main__":
    unittest.main()
