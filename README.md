# VOICE_TRANSLATION_COLLOL

Prototype Android voice-to-voice translation controlled by user A. The first demo targets a controlled VoIP/audio integration; user B does not install or control the translation tool.

## Repository layout

- `android/` — Kotlin/Jetpack Compose app boundary and VT-023 setup UI
- `backend/` — dependency-free health/smoke boundary; session service is not implemented yet
- `protocol/` — reserved for the VT-002 reviewed transport contract
- `research/` — audio-route and model benchmark harnesses
- `tools/` — repository checks

## Current verified app behavior

The Android debug build currently provides:

- A call-app picker populated from launchable apps visible on device A.
- A button to open the selected app.
- A/B language selection and swap.
- Local persistence of the selected app package and language choices using `SharedPreferences`.
- A fail-closed readiness check that does not capture, send, or translate audio.

The picker does **not** monitor calls in the background and does not inject audio into arbitrary third-party Android calling apps. The first real demo must use a VoIP integration controlled by the project, as required by the architecture notes.

## Development checks

```powershell
python -m backend.smoke
python tools/check_repo.py
python -m unittest research.audio_route.test_route -v
$env:ANDROID_HOME='C:/Users/Admin/AppData/Local/Android/Sdk'
./android/gradlew.bat -p android :app:assembleDebug :app:lintDebug
```

These checks do not prove real ASR/NMT/TTS inference, VoIP media injection, or the sub-second latency target.

## Remaining gates

- `VT-005`: controlled VoIP media-hook feasibility and device gates A–E.
- `VT-002` / `VT-004`: reviewed transport contract and architecture decision after VoIP evidence.
- `VT-011` / `VT-010` / `VT-012` / `VT-013`: audio lifecycle, session service, providers, and duplex orchestration after the gates.
- `VT-003`: real model benchmark remains blocked until model revisions, licensed corpus, hardware/runtime, and approved provider inputs are available.

## Branch and commit policy

Start from `origin/DEV`. Feature branches use `codex/VT-xxx` or `claude/VT-xxx`. Commits use `<area>: <feature> [VT-xxx]`. Only the general coordinator integrates reviewed commits into `DEV`.

Build Android: see `android/README.md`. Backend smoke: `python -m backend.smoke`.
