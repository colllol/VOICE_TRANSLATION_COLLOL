# VT-023 checkpoint - Voice Lab ASR start failure

- Date: 2026-10-27
- Owner: Codex
- Branch: `codex/VT-023-preview`
- Scope: Developer Voice Lab microphone handoff and ASR client error handling only.
- Diagnosis from supplied screenshot: ML Kit model download completed; Android SpeechRecognizer returned `ERROR_CLIENT` (code 5). Diagnostics `AudioRecord` had been active while ASR was starting.
- Changes: diagnostics recorder now has a release callback that waits for its read worker to exit and release `AudioRecord`; ASR starts only after that callback. A monotonically increasing run generation rejects stale model, ASR, translation and TTS callbacks after stop/restart. Restart during release is deferred. Client error retries once. RMS updates from recognizer callbacks.
- Tests: `:app:testDeveloperUnitTest`, `:app:assembleDeveloper`, `:app:lintDeveloper`, `:app:testDebugUnitTest`, `:app:assembleDebug`, `:app:lintDebug` passed. `pytest -q`: 177 passed. `python tools/check_repo.py`: passed. `python -m unittest release.test_audit -v`: 13 passed. `git diff --check`: passed.
- Device testing: intentionally not run, per user instruction.
- Release status: blocked. Audit requires device proof, controlled VoIP trace, model benchmark and latency measurement; none are available. The product is not verified as a complete production VoIP translator.
- Vault: configured Codex Knowledge path is unavailable in this environment; this checkpoint is local only and is not claimed synced.
- Next: independent review of final diff; commit only the scoped fix after review. Do not stage unrelated untracked files or run tests on a user device.
