"""A hung generator must cost its own feed, not the whole run.

Generators run one after another inside a single job, so a child that never
returns takes every feed queued behind it down with it. The only backstop used
to be the workflow's own timeout, which kills the run wholesale.
"""

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "feed_generators"))

import run_all_feeds  # noqa: E402
from models import FeedConfig  # noqa: E402


class GeneratorTimeoutTests(unittest.TestCase):
    def config(self):
        return FeedConfig(script="reuters.py", blog_url="https://example.test/")

    def test_a_hung_generator_is_reported_as_failed_not_raised(self):
        expired = subprocess.TimeoutExpired(cmd=["python"], timeout=1)
        with mock.patch.object(run_all_feeds.subprocess, "run", side_effect=expired):
            self.assertFalse(run_all_feeds.run_feed("reuters", self.config()))

    def test_output_produced_before_the_kill_is_still_relayed(self):
        expired = subprocess.TimeoutExpired(cmd=["python"], timeout=1)
        expired.stdout = "got 3 entries"
        expired.stderr = "warning: slow source"
        with mock.patch.object(run_all_feeds.subprocess, "run", side_effect=expired):
            with self.assertLogs(run_all_feeds.logger, level="WARNING") as caught:
                run_all_feeds.run_feed("reuters", self.config())
        relayed = "\n".join(caught.output)
        self.assertIn("got 3 entries", relayed)
        self.assertIn("warning: slow source", relayed)

    def test_a_generator_that_returns_in_time_is_unaffected(self):
        done = subprocess.CompletedProcess(args=["python"], returncode=0, stdout="", stderr="")
        with (
            mock.patch.object(run_all_feeds.subprocess, "run", return_value=done) as run,
            mock.patch.object(run_all_feeds, "_feed_pair_is_valid", return_value=True),
        ):
            self.assertTrue(run_all_feeds.run_feed("reuters", self.config()))
        # The timeout must actually be passed, or the guard is decorative.
        self.assertEqual(run.call_args.kwargs["timeout"], run_all_feeds.GENERATOR_TIMEOUT)

    def test_timeout_restores_both_artifacts_after_partial_child_write(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            xml = directory / "feed_reuters.xml"
            sidecar = directory / "feed_reuters.json"
            xml.write_text("old xml", encoding="utf-8")
            sidecar.write_text("old json", encoding="utf-8")

            def partial_then_timeout(*args, **kwargs):
                xml.write_text("new xml", encoding="utf-8")
                raise subprocess.TimeoutExpired(cmd=["python"], timeout=1)

            with (
                mock.patch.object(run_all_feeds, "FEEDS_DIR", directory),
                mock.patch.object(
                    run_all_feeds.subprocess, "run", side_effect=partial_then_timeout
                ),
            ):
                self.assertFalse(run_all_feeds.run_feed("reuters", self.config()))

            self.assertEqual(xml.read_text(encoding="utf-8"), "old xml")
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "old json")

    def test_success_with_invalid_pair_is_rolled_back(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            xml = directory / "feed_reuters.xml"
            sidecar = directory / "feed_reuters.json"
            xml.write_text("old xml", encoding="utf-8")
            sidecar.write_text("old json", encoding="utf-8")

            def invalid_success(*args, **kwargs):
                xml.write_text(
                    '<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>x</id></entry></feed>',
                    encoding="utf-8",
                )
                sidecar.write_text("not json", encoding="utf-8")
                return subprocess.CompletedProcess(
                    args=["python"], returncode=0, stdout="", stderr=""
                )

            with (
                mock.patch.object(run_all_feeds, "FEEDS_DIR", directory),
                mock.patch.object(run_all_feeds.subprocess, "run", side_effect=invalid_success),
            ):
                self.assertFalse(run_all_feeds.run_feed("reuters", self.config()))

            self.assertEqual(xml.read_text(encoding="utf-8"), "old xml")
            self.assertEqual(sidecar.read_text(encoding="utf-8"), "old json")


if __name__ == "__main__":
    unittest.main()
