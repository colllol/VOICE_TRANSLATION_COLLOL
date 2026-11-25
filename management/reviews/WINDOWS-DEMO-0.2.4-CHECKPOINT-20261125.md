# Windows demo checkpoint — 2026-11-25

## Scope

Windows laptop-first vertical slice: Kotlin/JVM 21 + Compose Desktop, Python FastAPI/WebSocket, SQLite operator storage, deterministic fake provider offline, and opt-in Azure provider boundary. No Android, VoIP SDK, or native SIP media integration is included in this checkpoint.

## Repository state

- Repository: `D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL`
- Branch: `dev-computer`
- Base tracking: `origin/dev-computer`
- Pre-existing dirty worktree contains Android, research, diagrams, generated data, and other rewrite files. Only the Windows/backend demo scope is intended for the associated commit.
- Vault path required by `AGENTS.md` was checked and is unavailable: `C:/Users/Admin/Documents/Codex Knowledge` does not exist. This checkpoint is local only; no vault synchronization is claimed.

## Verified implementation

- Compose Desktop launches the operator window and owns the packaged backend lifecycle.
- Backend is packaged as a PyInstaller onedir resource and started on loopback `127.0.0.1:8765`.
- Settings load/save through the UI and backend.
- WebSocket session start/stop works with backend-issued session IDs.
- Fake provider is the default and works offline; its voice test produces a deterministic local tone.
- Azure remains opt-in through environment configuration and is covered by HTTP-stub tests only. No Azure credential or live Azure request was used.

## Checks

- `py -3 -m pytest computer/server -q`: `71 passed, 60 warnings`.
- `py -3 -m compileall -q computer/server`: `PY_COMPILE_PASS`.
- `./gradlew clean test` from `computer-desktop`: `BUILD SUCCESSFUL`.
- `py -3 -m computer.server.desktop_smoke`: `BUILD SUCCESSFUL`; local temporary backend, SQLite, WebSocket, and Kotlin client smoke completed.
- `git diff --check`: `DIFF_CHECK_PASS`.

## GUI acceptance evidence

Built app-image:

`computer-desktop/build/compose/binaries/0.2.4/main-release/app/VoiceTranslationComputer/VoiceTranslationComputer.exe`

Observed in the interactive Windows desktop:

1. Window title `Voice Translation — Operator` appeared.
2. Bundled `VoiceTranslationBackend.exe` started and served `/health` and `/settings` on loopback.
3. UI showed `Backend: ready`, `Languages: vi → en`, and `Session stopped`.
4. `Start session` changed to an active session with a backend-issued ID and showed both offline test directions.
5. `Test mic: vi → en` entered `Recording for 4 seconds…` and finished with `Test tone played; no translation`.
6. `Stop session` returned the UI to `Session stopped`.
7. Closing the window shut down the owned backend. A final process check reported `NO_VOICE_TRANSLATION_PROCESS`; backend log ended with `Finished server process [18600]`.

This proves the local fake/offline GUI path. It does not prove intelligible translation, real microphone content, Azure live behavior, VoIP media injection, voice preservation, or sub-second end-to-end latency.

## Release artifacts

Built from the current source with Python 3.14 and PyInstaller:

- `computer-desktop/build/compose/binaries/0.2.4/main-release/exe/VoiceTranslationComputer-0.2.4.exe`
  - Size: `88752640` bytes
  - SHA-256: `803993c806a6827a2194c0723aa66c29864599af79a18747be101f9186f93dca`
- `computer-desktop/build/compose/binaries/0.2.4/main-release/msi/VoiceTranslationComputer-0.2.4.msi`
  - Size: `88068772` bytes
  - SHA-256: `9da949c86476bf43a2fe4eca34d61abc51ac1e1f42c6412daba40cb8d642da28`

`packageReleaseExe packageReleaseMsi` completed successfully. The MSI was not installed and user data was not deleted.

## Remaining gates

- Independent review and integration into `DEV` are not complete.
- Normal MSI install/upgrade/uninstall acceptance is not complete.
- Real microphone/speaker intelligibility and Azure live acceptance are not complete.
- Real VoIP peer/media-path acceptance is not complete.
- Latency target below one second and voice preservation remain unmeasured.
