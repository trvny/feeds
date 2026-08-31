import unittest
from pathlib import Path


class UpdateFeedsWorkflowTests(unittest.TestCase):
    def test_commit_requires_final_validation_and_non_cancelled_job(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "update-feeds.yml"
        ).read_text(encoding="utf-8")
        block = workflow.split("- name: Commit and push successful updates", 1)[1]
        block = block.split("- name: Apply feed health gate", 1)[0]

        self.assertIn("steps.validate.outcome == 'success'", block)
        self.assertIn("!cancelled()", block)


if __name__ == "__main__":
    unittest.main()
