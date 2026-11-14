# Rewrite checkpoint — dev-computer

Date: 2026-11-14

## Scope

Laptop-first replacement architecture: Python backend and Windows operator app. Android remains on the existing Kotlin/Jetpack Compose technology and will be ported only after the computer vertical slice is verified.

## Architecture decision

Use a versioned language-neutral wire contract. The backend owns session identity and lifecycle. A→B and B→A are independent streams. The Windows UI is an operator console, not the media engine. Controlled VoIP source/sink integration is a separate evidence gate.

The agent review recommends Kotlin Multiplatform + Compose Multiplatform for the Windows UI and shared client core, while keeping the backend in Python. This is a proposal; desktop UI has not been implemented yet.

## Implemented in this checkpoint

- `computer/server/contract.py`: versioned JSON envelope, audio format validation, frame-length validation, and no public transcript fields.
- `computer/server/coordinator.py`: server-issued session IDs, resume tokens, disconnect grace state, resume, and terminal cancellation.
- Tests were written before implementation and observed failing during RED; the minimal implementation now passes.

## Verification

- `python -m pytest computer/server -q`: 6 passed, 1 existing pytest deprecation warning.

## Not yet verified

- WebSocket transport and binary audio frames.
- Duplex translation workers and fake streaming providers.
- Windows app.
- Real ASR/NMT/TTS.
- Controlled VoIP media source/sinks, Android runtime, voice preservation, and sub-second latency.

## Blocker/context

The configured Codex Knowledge vault path was absent on this machine, so this checkpoint is local and does not claim vault synchronization.
