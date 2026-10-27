"""Executable VT-032 release and demo audit workflow.

The workflow keeps build, repository checks, artifact inspection, and external
proof as separate gates. It never turns synthetic tests into device evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import zipfile
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
REQUIRED_EVIDENCE = (
    "device_proof",
    "voip_trace",
    "model_benchmark",
    "latency_measurement",
)


def command_text(command: Sequence[str]) -> str:
    return subprocess.list2cmdline(list(command)) if os.name == "nt" else shlex.join(command)


def run_command(
    command: Sequence[str],
    cwd: Path = ROOT,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run one check and preserve enough output for an audit report."""
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
            env=env,
        )
    except OSError as exc:
        return {
            "status": "blocked",
            "command": command_text(command),
            "exit_code": None,
            "output": str(exc),
        }
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    unavailable = "No module named" in output or "command not found" in output
    return {
        "status": "blocked" if completed.returncode != 0 and unavailable else "passed" if completed.returncode == 0 else "failed",
        "command": command_text(command),
        "exit_code": completed.returncode,
        "output": output,
    }


def check_commands() -> list[tuple[str, list[str]]]:
    python = sys.executable
    return [
        ("release audit unit tests", [python, "-m", "unittest", "release.test_audit", "-v"]),
        ("repository policy and secret scan", [python, "tools/check_repo.py"]),
        ("backend import and health smoke", [python, "-m", "backend.smoke"]),
        ("backend and protocol pytest suite", [python, "-m", "pytest", "backend/", "protocol/", "-q"]),
        ("benchmark harness unit tests", [python, "-m", "unittest", "research.models.test_benchmark", "-v"]),
        ("VoIP route harness unit tests", [python, "-m", "unittest", "research.audio_route.test_route", "-v"]),
    ]


def android_command() -> list[str]:
    gradle = "android\\gradlew.bat" if os.name == "nt" else "android/gradlew"
    prefix = [] if os.name == "nt" else ["bash"]
    return prefix + [
        gradle,
        "-p",
        "android",
        ":app:assembleDebug",
        ":app:lintDebug",
        "--console=plain",
        "--no-daemon",
    ]


def android_check(root: Path = ROOT) -> dict[str, Any]:
    sdk = next(
        (
            value
            for value in (os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"))
            if value and Path(value).is_dir()
        ),
        None,
    )
    if sdk is None:
        properties = root / "android" / "local.properties"
        try:
            for line in properties.read_text(encoding="utf-8").splitlines():
                key, separator, value = line.partition("=")
                if separator and key.strip() == "sdk.dir":
                    sdk = _unescape_property(value.strip())
                    if sdk and not Path(sdk).is_absolute():
                        sdk = str((properties.parent / sdk).resolve())
                    break
        except OSError:
            pass
    if not sdk or not Path(sdk).is_dir():
        return {
            "status": "blocked",
            "command": command_text(android_command()),
            "exit_code": None,
            "output": "Android SDK not found; set ANDROID_HOME or ANDROID_SDK_ROOT, or configure android/local.properties.",
        }
    gradle_env = os.environ.copy()
    gradle_env["ANDROID_HOME"] = sdk
    gradle_env["ANDROID_SDK_ROOT"] = sdk
    return run_command(android_command(), cwd=root, env=gradle_env)


def _unescape_property(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        index += 1
        if char != "\\" or index == len(value):
            result.append(char)
            continue
        escaped = value[index]
        index += 1
        if escaped == "u" and index + 4 <= len(value):
            digits = value[index:index + 4]
            try:
                result.append(chr(int(digits, 16)))
                index += 4
                continue
            except ValueError:
                result.extend(("\\", escaped))
                continue
        result.append(escaped)
    return "".join(result)


def run_checks(root: Path = ROOT, dry_run: bool = False, include_android: bool = False) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    planned = check_commands()
    if include_android:
        planned.append(("Android debug APK and lint", android_command()))
    for name, command in planned:
        if dry_run:
            checks.append({"name": name, "status": "planned", "command": command_text(command)})
        else:
            result = android_check(root) if name == "Android debug APK and lint" else run_command(command, cwd=root)
            result["name"] = name
            checks.append(result)
    return {
        "dry_run": dry_run,
        "checks": checks,
        "status": "dry-run" if dry_run else overall_check_status(checks),
    }


def overall_check_status(checks: Sequence[dict[str, Any]]) -> str:
    statuses = {check.get("status") for check in checks}
    if "failed" in statuses:
        return "failed"
    if "blocked" in statuses:
        return "blocked"
    return "passed"


def artifact_summary(path: Path) -> dict[str, Any]:
    path = path.resolve()
    if not path.is_file():
        return {
            "status": "not-produced",
            "path": str(path),
            "size_bytes": None,
            "sha256": None,
            "zip_integrity": None,
        }

    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)

    zip_integrity = "not-a-zip"
    required_entries: list[str] = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            bad_entry = archive.testzip()
            zip_integrity = "passed" if bad_entry is None else f"failed: {bad_entry}"
            names = set(archive.namelist())
            required_entries = [name for name in ("AndroidManifest.xml",) if name in names]

    status = "passed" if zip_integrity == "passed" and "AndroidManifest.xml" in required_entries else "failed"
    return {
        "status": status,
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": digest.hexdigest(),
        "zip_integrity": zip_integrity,
        "required_entries": required_entries,
    }


def evidence_file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def evidence_status(evidence: dict[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    invalid: list[str] = []
    for name in REQUIRED_EVIDENCE:
        item = evidence.get(name)
        if not item:
            missing.append(name)
            continue
        if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
            invalid.append(name)
            continue
        path = Path(str(item["path"])).expanduser()
        try:
            valid_file = path.is_file() and evidence_file_sha256(path) == str(item["sha256"]).lower()
        except OSError:
            valid_file = False
        if not valid_file:
            invalid.append(name)
    return {
        "status": "passed" if not missing and not invalid else "blocked",
        "missing": missing,
        "invalid": invalid,
        "required": list(REQUIRED_EVIDENCE),
        "note": "External evidence requires an existing file and matching SHA-256; synthetic tests and an APK do not satisfy this gate.",
    }


def load_evidence(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"_load_error": str(exc)}


def report_status(check_status: str, artifact_status: str, evidence_gate: str) -> str:
    if check_status == "failed" or artifact_status == "failed":
        return "failed"
    if check_status == "blocked" or artifact_status != "passed" or evidence_gate == "blocked":
        return "blocked"
    return "passed"


def build_report(
    root: Path = ROOT,
    *,
    dry_run: bool = False,
    include_android: bool = False,
    artifact: Path | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = run_checks(root, dry_run=dry_run, include_android=include_android)
    artifact_result = artifact_summary(artifact or (root / DEFAULT_ARTIFACT.relative_to(ROOT))) if not dry_run else {
        "status": "not-inspected",
        "path": str(artifact or DEFAULT_ARTIFACT),
    }
    proof = evidence_status(evidence or {}) if not dry_run else {
        "status": "not-inspected",
        "missing": list(REQUIRED_EVIDENCE),
        "required": list(REQUIRED_EVIDENCE),
    }
    status = "dry-run" if dry_run else report_status(
        checks["status"], artifact_result["status"], proof["status"]
    )
    return {
        "status": status,
        "preview": True,
        "checks": checks,
        "artifact": artifact_result,
        "external_evidence": proof,
        "limitations": [
            "The current APK is a VT-023 setup preview, not a complete VoIP translator.",
            "No real ASR/NMT/TTS benchmark, controlled VoIP media proof, or device call trace is implied.",
            "The sub-second latency target is unmeasured.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the VT-032 release/demo audit.")
    parser.add_argument("--dry-run", action="store_true", help="List checks without executing commands.")
    parser.add_argument("--android-build", action="store_true", help="Include the Android build/lint gate.")
    parser.add_argument("--artifact", type=Path, help="APK or other produced artifact to inspect.")
    parser.add_argument("--evidence", type=Path, help="JSON evidence manifest for external proof gates.")
    parser.add_argument("--report", type=Path, help="Write the JSON report to this path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(
        dry_run=args.dry_run,
        include_android=args.android_build,
        artifact=args.artifact,
        evidence=load_evidence(args.evidence),
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] in {"passed", "dry-run", "blocked"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
