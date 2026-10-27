# VT-032 release and demo audit

This is an executable audit for the current preview state. It does not turn a debug APK, fake-provider tests, or route-harness tests into proof of a working translated call.

## Scope and status

The current deliverable is a VT-023 Android setup preview. It can select/open a launchable app, select languages, persist local choices, and report fail-closed local readiness. It does not capture or inject audio, monitor calls, connect two peers, run real ASR/NMT/TTS inference, or demonstrate the sub-second latency target.

The following external evidence is required before calling the demo complete:

- `device_proof`: a reproducible A-device install/launch/call trace, with no personal audio committed.
- `voip_trace`: controlled VoIP media-path evidence for both directions, including consent and frame/timestamp or checksum data.
- `model_benchmark`: approved model revisions, corpus/license, hardware/runtime, and measured ASR/NMT/TTS results.
- `latency_measurement`: measured end-to-end latency for the stated target and test conditions.

Evidence is accepted only through a JSON manifest whose paths exist and whose SHA-256 values match. Start from [`release/evidence.example.json`](../../release/evidence.example.json); keep private recordings and credentials outside the repository.

## Prerequisites

- Python 3.10+.
- Python dependencies from `backend/requirements.txt` and `pytest` for the backend/protocol suite. The audit script itself uses only the Python standard library.
- JDK 21 and Android SDK platform 36/build-tools 36.0.0 for the Android gate. Set `ANDROID_HOME` or provide `android/local.properties`; `android/local.properties` is ignored and must not be committed.

## Run the audit

From the repository root:

```text
python -m release.audit --help
python -m release.audit --dry-run
python -m unittest release.test_audit -v
python -m release.audit --android-build --report release/audit-report.json
```

The last command runs the repository checks, research unit tests, Android debug build/lint, APK inspection, and the external-evidence gate. It returns zero for a blocked external gate so the report can be inspected; it returns non-zero for a failed check or invalid produced artifact. A blocked Android prerequisite is recorded as `blocked`, never as a successful build.

The report includes each exact command and exit code, artifact path/size/SHA-256 when an APK exists, ZIP integrity and `AndroidManifest.xml` presence, and the missing/invalid evidence items.

## Direct repository checks

These are the same non-Android checks used by the audit:

```text
python tools/check_repo.py
python -m backend.smoke
python -m pytest backend/ protocol/ -q
python -m unittest research.models.test_benchmark -v
python -m unittest research.audio_route.test_route -v
```

The fake-provider and route-harness tests are contract checks only. They do not prove real providers, a native VoIP path, or a device call.

## Android artifact gate

The canonical build is:

- Windows: `android\\gradlew.bat -p android :app:assembleDebug :app:lintDebug --console=plain --no-daemon`
- Linux/macOS: `bash android/gradlew -p android :app:assembleDebug :app:lintDebug --console=plain --no-daemon`

Expected output: `android/app/build/outputs/apk/debug/app-debug.apk`. The audit computes the finished file's exact byte size and SHA-256 and checks that it is a readable ZIP containing `AndroidManifest.xml`. Generated APKs and Gradle build output are ignored and are not committed.

A successful build proves compilation/lint and artifact integrity only. It does not prove VoIP, model, latency, consent, or device evidence.

## Demo operator script

1. Install the debug APK on device A using an approved, non-personal test device and record the APK SHA-256.
2. Launch the app. Select the controlled call app exposed by the device and select A/B languages.
3. Confirm the app's fail-closed readiness result. Do not describe this as a connected or translated call.
4. If the controlled VoIP integration is available, run its approved two-direction call procedure and collect external evidence separately.
5. Stop if the controlled integration, device permissions, model providers, or evidence capture are unavailable. Do not substitute screenshots, fake audio, or route-harness output for the missing gates.
6. Populate an evidence manifest with files and exact SHA-256 values, then rerun `python -m release.audit --evidence <manifest> --artifact <apk>`.

## Audit interpretation

- `passed`: the requested local gate ran successfully.
- `blocked`: a prerequisite or required external evidence is absent; this is not a pass.
- `failed`: a command or produced artifact failed verification.
- `preview: true`: this branch documents and audits the current preview; it is not a complete VoIP release.
