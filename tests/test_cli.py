import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tapsroute import cli
from tapsroute.core import Store, approve, new_post, schedule_at

class CliSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "state.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_test_mode_records_dry_run_without_changing_post_status(self):
        post = new_post(
            "Goa", "Weekend trips", "English", ["facebook"], "Sample Goa trip",
            "Sample planning content", [], "Explore", "AI Goa image", schedule_at(date(2020, 1, 1), "10:00"),
            image_path="images/goa.jpg", image_url="https://example.org/goa.jpg",
        )
        self.store.change(lambda data: data["posts"].append(post))
        approve(self.store, post["id"], "owner")
        with patch.dict(os.environ, {"TEST_MODE": "true"}), patch("tapsroute.cli.Store", return_value=self.store):
            cli.publish_due(SimpleNamespace())
        saved = self.store.read()
        self.assertEqual(saved["posts"][0]["status"], "SCHEDULED")
        self.assertEqual(saved["posts"][0]["platform_status"]["facebook"]["status"], "PENDING")
        self.assertEqual(saved["events"][-1]["type"], "PUBLISH_DRY_RUN")

if __name__ == "__main__":
    unittest.main()
