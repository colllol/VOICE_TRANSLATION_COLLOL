# VT-005 Windows VoIP Spike Results

Date: 2026-11-23 (Asia/Ho_Chi_Minh)
Scope: Windows-first discovery for `research/audio_route/windows-voip-design.md`; no product integration or dependency artifacts.

## Contract under test
A controls translation; B uses an ordinary SIP client. `a2b` replaces A microphone audio before call encoding/transmission; `b2a` replaces B decoded media before A playback. Direction sequence/state stays separate. ASR/NMT text is internal only. When translation is active, provider failure must not silently forward original speech; A's explicit stop restores ordinary audio.

## Baresip
- Upstream repository reports BSD 3-Clause, SIP user-agent, modular audio and Windows WASAPI driver.
- Upstream module tree has `wasapi`, `ausrc`, `auplay`, and filter modules; source audio is allocated through an `ausrc` callback, and the `aufile` example registers both source and playback modules.
- This supports a plausible Windows integration point, but retrieved documentation does not establish a per-call, independent pre-encoder outbound hook and decoded per-call inbound replacement for the exact contract. Do not claim the hook is proven until a custom module is built and exercised during a SIP call.
- Built Baresip 4.13.0 (`285493137eec82f54f13881294e72aaf617e1294`) with MSYS2 UCRT64 GCC 16.1, CMake 4.3.2 and Ninja. Built static libre (`c55e00a3806f473fbb32a7309fc5ccee944a5228`) with `USE_SIP=ON` and `USE_REM=ON`. Disabling REM produced unresolved audio symbols at link time. WASAPI compiled and linked. Physical microphone and speaker behavior remains unverified.

## Reproduce the Windows SIP fixture

In Git Bash from the repository root, set `scratch` to an existing scratch root with the pinned checkouts in `libre-src` and `baresip-src`. Use Windows-style paths. The probe creates two disposable profiles bound to loopback. Both send synthetic sine waves, and only A loads the filter in the replacement case. Temporary WAV outputs are removed after the run.

```bash
export PATH=/c/msys64/ucrt64/bin:$PATH
repo=$(git rev-parse --show-toplevel)
cmake -S "$scratch/libre-src" -B "$scratch/libre-build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$scratch/prefix" \
  -DLIBRE_BUILD_STATIC=ON -DLIBRE_BUILD_SHARED=OFF -DUSE_SIP=ON \
  -DUSE_REM=ON -DUSE_BFCP=OFF -DUSE_PCP=OFF -DUSE_RTMP=OFF
cmake --build "$scratch/libre-build" --parallel 6
cmake --install "$scratch/libre-build"
cmake -S "$scratch/baresip-src" -B "$scratch/baresip-build" -G Ninja \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$scratch/prefix" -DSTATIC=ON \
  -DMODULES='account;g711;menu;wasapi;ausine;aufile' \
  -DAPP_MODULES=vt005_probe -DAPP_MODULES_DIR="$repo/research/audio_route/baresip_modules"
cmake --build "$scratch/baresip-build" --target baresip_exe --parallel 6
C:/Python314/python.exe research/audio_route/windows_sip_probe.py "$scratch/baresip-build/baresip.exe" "$scratch"
C:/Python314/python.exe research/audio_route/windows_sip_probe.py "$scratch/baresip-build/baresip.exe" "$scratch" --replacement
```

Both peers established SIP calls and logged a mono PCMU encoder and decoder at 8 kHz. With the filter off, the one-second windows contained the opposite peer's tone (700 Hz at A, 400 Hz at B), with sample ranges `[-8316, 8316]`. With the filter active on A, B measured `3004` (G.711 quantization of the outbound fixture `3000`) and A measured `-3000` (inbound fixture). Each window had 8,000 samples. Both runs passed with `python -O`. As a negative control on the same binary, adding `--replacement --omit-filter` exited 1 with `Peer a: 8000 off-target samples`. This checks the selected WAV windows only, not startup, teardown, or failures in a real call.

## PJSIP/PJSUA2 fallback
- Existing Android spike built PJSIP 2.17 for Android arm64 and confirmed `AudioMediaPort::onFrameRequested` / `onFrameReceived` symbols; this is not Windows build evidence.
- Official PJSIP licensing says GPL v2-or-later or proprietary licensing arranged with Teluu. The project R&D/community intent does not alone establish that the complete distributed application and derivative/linking terms comply. No PJSIP binary/source was added here.
- Treat PJSIP as the clearer documented media-port fallback only after the owner approves a GPL-compatible distribution and reviews all included third-party notices, or authorizes a Teluu license route.

## Existing harness verification
`C:/Python314/python.exe -m pytest research/audio_route -q --tb=short` returned `13 passed in 0.05s`. This suite covers the Python route harness with synthetic PCM.

After adding four probe checks (wrong direction at either sink, one off-target sample, and truncation), `C:/Python314/python.exe -m pytest research/audio_route computer/server -q --tb=short` returned `81 passed, 51 warnings`. No live provider was exercised by these checks.

## Result
**Windows SIP fixture passed. Product acceptance is pending.** The fixture validates bidirectional substitution in a native Baresip loopback call. A live provider, product integration, WASAPI playback and capture, and an independent B endpoint remain unverified. No real-call latency, interruption or intelligibility measurements exist.

## Remaining owner acceptance
1. Connect the Windows SIP path to the translation backend and verify physical capture and playback.
2. Test independent `a2b` and `b2a` translation, stop, provider failure, reconnect and cleanup.
3. Place an actual call from A's controlled Baresip/PJSIP endpoint to B's ordinary SIP client. Verify audio at both endpoints and measure directional latency, interruption and intelligibility. Do not save personal recordings, transcripts, or credentials.
4. If Baresip cannot prove the required PCM hook, evaluate PJSIP on Windows only after the GPL/commercial licensing route is explicitly approved.
5. Independent review and owner confirmation are still required before closing VT-005. Android remains out of scope until Windows behavior is accepted.

## Sources
- Baresip repository and module tree: https://github.com/baresip/baresip and https://github.com/baresip/baresip/tree/main/modules
- Baresip audio allocation and `aufile` example: https://github.com/baresip/baresip/blob/main/src/audio.c and https://github.com/baresip/baresip/blob/main/modules/aufile/aufile.c
- PJSIP official license: https://www.pjsip.org/licensing.htm
- PJSIP official audio frame API: https://docs.pjsip.org/en/latest/specific-guides/audio/audio_frame_manipulation.html
