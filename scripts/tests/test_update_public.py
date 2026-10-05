"""Exercise unattended updates without credentials or source access."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location("update_public", Path(__file__).parents[1] / "update_public.py")
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdaterTests(unittest.TestCase):
    def test_server_imports_immediately_then_waits_and_recovers_from_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = Mock()
            stop.wait.side_effect = [False, True]
            publish = Mock(side_effect=[RuntimeError("private source failure"), None])
            with patch.object(updater, "PRIVATE", Path(directory)), patch.object(updater, "STOP", stop), patch.object(updater, "save") as save, patch.object(updater, "publish", publish), patch.object(updater.signal, "signal"), patch("builtins.print"):
                updater.run(interval=300, initial=True, follow_main=True)
            self.assertEqual(publish.call_count, 2)
            publish.assert_called_with(sync=True, follow_main=True)
            self.assertEqual(stop.wait.call_args_list[0].args, (300,))
            self.assertTrue(any(call.kwargs.get("error") for call in save.call_args_list))
            self.assertEqual(save.call_args_list[-1].kwargs, {"running": False, "pid": None})

    def test_dirty_server_checkout_prevents_source_fetch_and_publication(self):
        with patch.object(updater, "checked", return_value=" M docs/assets/app.js") as checked:
            with self.assertRaisesRegex(RuntimeError, "working_tree_changes_present"):
                updater.publish(sync=True, follow_main=True)
        self.assertEqual(checked.call_count, 1)

    def test_failed_sync_never_exports_or_commits_a_partial_snapshot(self):
        def checked(args, **kwargs):
            if "sync" in args:
                raise RuntimeError("source_failed")
            return ""
        with patch.object(updater, "checked", side_effect=checked) as calls:
            with self.assertRaises(RuntimeError):
                updater.publish(sync=True, follow_main=True)
        commands = [call.args[0] for call in calls.call_args_list]
        self.assertFalse(any("export-public" in cmd or "commit" in cmd for cmd in commands))
        self.assertEqual(sum("pull" in cmd for cmd in commands), 2)


if __name__ == "__main__":
    unittest.main()
