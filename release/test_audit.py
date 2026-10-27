import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release import audit


class AuditTests(unittest.TestCase):
    def test_sha256_reports_exact_size_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "app-debug.apk"
            artifact.write_bytes(b"apk fixture")

            result = audit.artifact_summary(artifact)

        self.assertEqual(result["size_bytes"], 11)
        self.assertEqual(
            result["sha256"],
            hashlib.sha256(b"apk fixture").hexdigest(),
        )

    def test_missing_evidence_is_blocked(self):
        result = audit.evidence_status({"device_proof": "", "voip_trace": ""})

        self.assertEqual(result["status"], "blocked")
        self.assertIn("device_proof", result["missing"])
        self.assertIn("voip_trace", result["missing"])

    def test_unverifiable_evidence_labels_are_blocked(self):
        evidence = {name: "claimed" for name in audit.REQUIRED_EVIDENCE}

        result = audit.evidence_status(evidence)

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(set(result["invalid"]), set(audit.REQUIRED_EVIDENCE))

    def test_evidence_files_require_matching_sha256(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence_file = Path(directory) / "proof.txt"
            evidence_file.write_bytes(b"external proof")
            digest = hashlib.sha256(b"external proof").hexdigest()
            evidence = {
                name: {"path": str(evidence_file), "sha256": digest}
                for name in audit.REQUIRED_EVIDENCE
            }

            result = audit.evidence_status(evidence)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["invalid"], [])

    def test_missing_android_sdk_is_blocked_without_running_gradle(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            audit.os.environ, {"ANDROID_HOME": "", "ANDROID_SDK_ROOT": ""}
        ), patch.object(audit, "run_command") as run_command:
            result = audit.android_check(Path(directory))

        run_command.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("ANDROID_HOME", result["output"])

    def test_android_sdk_local_properties_fallback_runs_gradle(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk"
            sdk.mkdir()
            android = root / "android"
            android.mkdir()
            (android / "local.properties").write_text(
                f"sdk.dir={sdk.as_posix()}\n",
                encoding="utf-8",
            )
            expected = {"status": "passed", "exit_code": 0}
            with patch.dict(
                audit.os.environ, {"ANDROID_HOME": "", "ANDROID_SDK_ROOT": ""}
            ), patch.object(audit, "run_command", return_value=expected) as run_command:
                result = audit.android_check(root)

        run_command.assert_called_once()
        self.assertEqual(result["status"], "passed")

    def test_invalid_android_home_falls_back_to_valid_sdk_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "sdk"
            sdk.mkdir()
            with patch.dict(
                audit.os.environ,
                {"ANDROID_HOME": str(root / "missing"), "ANDROID_SDK_ROOT": str(sdk)},
            ), patch.object(
                audit, "run_command", return_value={"status": "passed"}
            ) as run_command:
                result = audit.android_check(root)

        run_command.assert_called_once()
        self.assertEqual(result["status"], "passed")

    def test_invalid_environment_sdk_falls_back_to_escaped_local_properties(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = root / "Android SDK"
            sdk.mkdir()
            android = root / "android"
            android.mkdir()
            escaped = str(sdk).replace("\\", "\\\\").replace(" ", "\\ ")
            (android / "local.properties").write_text(
                f"sdk.dir={escaped}\n",
                encoding="utf-8",
            )
            with patch.dict(
                audit.os.environ,
                {"ANDROID_HOME": str(root / "missing"), "ANDROID_SDK_ROOT": ""},
            ), patch.object(
                audit, "run_command", return_value={"status": "passed"}
            ) as run_command:
                result = audit.android_check(root)

        run_command.assert_called_once()
        self.assertEqual(result["status"], "passed")

    def test_dry_run_does_not_execute_commands(self):
        with patch.object(audit, "run_command") as run_command:
            result = audit.run_checks(Path("."), dry_run=True)

        run_command.assert_not_called()
        self.assertTrue(result["dry_run"])
        self.assertGreaterEqual(len(result["checks"]), 1)

    def test_report_is_json_serializable(self):
        report = audit.build_report(Path("."), dry_run=True)

        json.dumps(report)
        self.assertEqual(report["status"], "dry-run")

    def test_missing_artifact_keeps_release_blocked(self):
        status = audit.report_status("passed", "not-produced", "passed")

        self.assertEqual(status, "blocked")

    def test_invalid_artifact_fails_release(self):
        status = audit.report_status("passed", "failed", "blocked")

        self.assertEqual(status, "failed")


if __name__ == "__main__":
    unittest.main()
