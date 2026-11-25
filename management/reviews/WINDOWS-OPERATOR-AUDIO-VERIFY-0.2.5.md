# Checkpoint — Windows operator audio verification (0.2.5)

Date: 2026-11-25
Branch: `dev-computer` (local commit only; not pushed — GM merges into `DEV`)
Vault: `C:/Users/Admin/Documents/Codex Knowledge` does not exist on this host, so this
checkpoint lives in `management/reviews/` per `AGENTS.md` and is **not** synced to the vault.

## Why

The operator could not verify three things on 0.2.4:

1. Microphone test produced no numbers and no UI, so success was indistinguishable from silence.
2. Speaker test beeped once and stopped; unclear whether it was broken or the regression test
   was missing.
3. No way to see what the audio pipeline was actually doing.

## Root causes found in code

| Symptom | Cause |
| --- | --- |
| Speaker "beeps once" | `FakeTranslationProvider` synthesised a fixed **4000 samples** = **250 ms** at 16 kHz, so the round trip played a quarter second of tone regardless of how long the operator spoke. |
| Mic test unverifiable | Capture returned a byte array only; no RMS/peak/silence measurement reached the UI. |
| Pipeline opaque | No device names, no format, no per-stage timing surfaced to the operator. |

## Changes

- `computer/server/providers.py` — fake provider tone length now follows the captured audio,
  clamped to 1000–4000 ms, with a 5 ms fade each way to avoid speaker pops.
- `computer-desktop/.../LocalVoiceAudio.kt` — `CaptureInfo` (device, bytes, duration, RMS dBFS,
  peak dBFS, silent ratio) and `PlaybackInfo` (device, bytes, expected vs played ms, `complete`);
  `deviceName()` resolves the real mixer name; 1 s standalone tone generator.
- `computer-desktop/.../Main.kt` — "Test speaker: 1 s tone" button independent of session/mic;
  mic test reports the measurements and refuses to send audio when ≥95 % of frames are silent;
  "Audio pipeline" panel traces device selection, format, session/provider, backend round trip
  and playback duration.
- `computer-desktop/build.gradle.kts` — version `0.2.4` → `0.2.5`.
- New `LocalVoiceAudioMetricTest.kt` — pins the measurement maths and the tone length.

## Verification (measured, this host)

- `./gradlew test` — BUILD SUCCESSFUL; `LocalVoiceAudioMetricTest` 5 tests, `BackendClientTest` 4,
  `SessionClientTest` 4 → **13 tests, 0 failures**.
- `py -3 -m pytest computer/server -q` — **72 passed**.
- `./gradlew packageReleaseMsi -PpythonExecutable=<venv with PyInstaller 6.22.3>` — BUILD SUCCESSFUL,
  `build/compose/binaries/0.2.5/main-release/msi/VoiceTranslationComputer-0.2.5.msi` (73,505,657 bytes).
- MSI metadata read back via `WindowsInstaller.Installer`:
  `ProductVersion=0.2.5`, `ProductCode={07813C57-5FF9-3B45-AEE5-F76CC1301597}` — differs from the
  installed 0.2.4 `{25809A21-A420-3DD5-8FE1-DD158D34EAF7}`, so Windows Installer will not block
  the upgrade the way it blocked the same-ProductCode 0.2.4 build.

## Not verified — requires the operator at the device

- Whether the 1 s tone is audible on the actual Windows output device, and whether the 4 s mic
  capture reports plausible dBFS on the real microphone. No agent-side audio device access.
- No claim is made about latency < 1 s, real voice preservation, VoIP injection or AEC.

## Next step for the operator

Close the running 0.2.4 process, install the 0.2.5 MSI, then: Check backend → Start session →
Test speaker → Test mic. The trace panel shows the numbers; a silent capture or a short playback
now states its own cause instead of failing quietly.
