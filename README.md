# VOICE_TRANSLATION_COLLOL

Prototype Android voice-to-voice translation controlled by user A. The first demo targets a controlled VoIP/audio integration; user B does not install or control the translation tool.

## Repository layout

- `android/` — Kotlin/Jetpack Compose app boundary (scaffold in VT-001)
- `backend/` — FastAPI/WebSocket service boundary
- `protocol/` — versioned transport contracts and fixtures
- `tools/` — repository checks

## Development checks

```powershell
python tools/check_repo.py
```

The check flags selected inline secret patterns and verifies required project boundaries. It does not claim that Android build or VoIP routing is implemented.

## Branch and commit policy

Start from `origin/DEV`. Feature branches use `codex/VT-xxx` or `claude/VT-xxx`. Commits use `<area>: <feature> [VT-xxx]`. Only the general coordinator integrates reviewed commits into `DEV`.

## Current status

This repository contains an Android development screen and a dependency-free backend smoke scaffold. Model selection, Android audio routing, controlled VoIP injection, ASR/NMT/TTS providers, and benchmark results remain pending their tickets.

Build Android: xem android/README.md. Backend smoke: python -m backend.smoke.
Các dịch vụ và model chưa được triển khai; app hiện chỉ là màn hình trạng thái phát triển.
