# Windows Native IPC Checkpoint

Date: 2026-11-23 (Asia/Ho_Chi_Minh)
Task: VT-005 Windows Baresip <-> Python PCM IPC integration
Scope: `research/audio_route/` and this checkpoint. No commit made.

## Result

The synthetic native SIP replacement, baseline, and disconnect probes pass after a clean Baresip rebuild. This is deterministic loopback evidence only, not a real provider, device, or human-call acceptance.

## Root cause and correction

Investigation identified lifecycle risks in intermediate implementations: blocking socket operations during teardown, competing socket ownership, and queued entries retained after connection failure. These were corrected together; no single-variable experiment establishes which defect caused the original WinError 64/hang, so that historical root cause remains unisolated. The worker is now the sole socket closer, performs bounded nonblocking connect/send/receive outside the audio callback, drops stale queued data on disconnect, and exits before per-lane events/critical section are destroyed. Encoder and decoder retain independent queues/workers/ports. The callback uses a bounded queue and TryEnterCriticalSection, does no socket I/O or allocation, and emits silence on underrun. Native transport is explicit mono S16LE 8 kHz (`VT08`); it does not pretend to satisfy the backend's existing 16 kHz contract.

The original baseline harness inadvertently loaded the replacement filter even in baseline mode, so the expected ordinary 700 Hz source tone was replaced/silenced. Baseline mode now omits the filter. Replacement fixture tones use continuous phase across frames.

## Verification

- Clean native build: `cmake --build .../vt005-independent-build-clean -j 4`; exit 0, no warnings.
- Baseline: both peers recorded 8,000 samples, range `[-8316, 8316]`; expected 700/400 Hz tone assertions passed.
- Replacement: both peers recorded 8,000 samples; ranges A `[-5000, 5000]`, B `[-5116, 5116]`; direction-specific 660/440 Hz replacement assertions passed.
- Disconnect: both peers recorded 8,000 samples; ranges A `[0, 0]`, B `[2, 2]`; no stale/ordinary PCM leakage beyond the 2-LSB threshold.
- Repeated replacement/disconnect/replacement also passed, exercising reconnection and repeated teardown.
- Python regression suite: `C:/Python314/python.exe -m pytest research/audio_route -q --tb=short`; **25 passed in 0.47s**.

## Limits and ownership

- Only synthetic PCM loopback was tested. No physical WASAPI path, live translation provider, 16 kHz conversion, sub-second latency, real remote SIP device, intelligibility, or human-call behavior is claimed.
- The required vault path `C:/Users/Admin/Documents/Codex Knowledge` was unavailable in this session; this checkpoint is local only and not synchronized to the vault.
- Existing unrelated dirty-worktree changes were preserved. No commit or push was made.
