# Checkpoint long-run app completion — 2026-10-17

- Goal: tiếp tục hoàn thiện app theo DAG, không giới hạn ở UI preview; không đánh Done nếu thiếu runtime evidence.
- Branch `codex/VT-023-preview`; commits mới trong nhánh: `21d215b` app picker preview, `0e34d88` persist app/lang config locally, `5b60d5e` README evidence, `1242365` refresh app list on resume. Nhánh ahead origin/DEV 6 commits; không push/merge theo rule.
- App picker enumerates launchable packages with Android `<queries>`, excludes itself, shows icon/label/package and launches selected app. Background call/audio monitor intentionally not implemented or claimed.
- Selected app package and A/B languages persist via SharedPreferences. App list refreshes on Activity resume; selected package resolves against current installed launcher list.
- Latest `assembleDebug + lintDebug`: PASS 48 tasks, 13 executed; only two existing `Modifier.menuAnchor()` deprecation warnings.
- `python -m backend.smoke`: PASS (health import only); `python tools/check_repo.py`: PASS; route harness tests: PASS 13/13; `git diff --check`: PASS.
- ADB was restarted during app-picker install attempt; currently `adb devices -l` and mDNS empty. Therefore new picker/persistence has not been visually/device-tested on Redmi yet; earlier preview device smoke predates new picker.
- Runtime status rechecked: no NDK/PJSIP SDK/media integration, no second peer B, no model/revision/corpus/provider configuration proven. Do not start AudioRecord/foreground monitoring against arbitrary apps or claim injection.
- Remaining major DAG: VT-005 actual controlled VoIP proof A-E; VT-003 real inference benchmark; VT-002 transport contract after 005; VT-004 architecture gate; then VT-011/010/012/013/014 and later quality/privacy gates.
- Need external owner inputs/environment: reconnect/unlock/approve Redmi Wireless debugging; select controlled VoIP SDK and provide compatible peer B; approved model/revision, licensed corpus and provider billing/credentials for real benchmark. Never record secret values.

## 2026-10-17 — Tiếp tục hoàn thiện app / trạng thái ngoài repo
- Đã bổ sung picker chọn app gọi có thể mở, nút Mở, package visibility Android 11+, lưu package/ngôn ngữ bằng SharedPreferences, refresh app list ở Activity resume; commit `21d215b`, `0e34d88`, `1242365`. README chính xác hóa trạng thái ở `5b60d5e`.
- Build/lint pass 48 tasks; backend smoke + repo check pass; route harness 13/13 pass. Hai warning `Modifier.menuAnchor()` deprecated.
- App picker mới chưa có device smoke vì ADB device/mdns hiện rỗng sau `adb start-server`. PC Wi-Fi hiện `192.168.100.23`; endpoint lịch sử `192.168.100.213:40363` trả TCP false / ADB connection refused 10061; endpoint cũ `192.168.0.51` cũng unreachable. Không retry mã/cổng cũ.
- PJSIP source probe thất bại: `curl -I -L https://github.com/pjsip/pjproject/releases/latest` không qua được proxy `127.0.0.1:9`. NDK/PJSIP SDK chưa cài, peer B chưa có.
- Dependencies inference `faster_whisper`, `transformers`, `ctranslate2`, `sentencepiece`, `datasets` không có trong Python; chỉ torch importable. Không có benchmark inference thật.
- Goal hoàn thiện app còn active; VT-005 device proof và VT-003 model benchmark blocked. Không đánh Done, không push/merge.

## 2026-10-17 — PJSIP 2.17 feasibility check
- Direct `git -c http.proxy= ls-remote https://github.com/pjsip/pjproject.git refs/tags/2.17` succeeded; source cloned only to `C:/Users/Admin/AppData/Local/Temp/pjproject-2.17-vt005`, not repo.
- PJSIP 2.17 source exposes `pjsua2::AudioMediaPort::onFrameRequested` and `onFrameReceived`, with `createPort`/conference bridge; this is a viable controlled-VoIP media-hook candidate, not proof of Android integration.
- `COPYING` is GNU GPL v2 for the project source. No license decision made for this app distribution; do not vendor/link PJSIP into APK until product/license review approves it and notices/source obligations are planned.
- `configure-android` and `pjsip-apps/src/samples/android_sample` exist, but local Android SDK has no NDK/cmdline-tools and no PJSIP binary/AAR. No build performed.
- No peer B or controlled SIP endpoint is available; gates A–E remain unrun. AudioTrack/third-party call interception remains unsupported claim.

## 2026-10-17 — PJSIP media hook verified, integration not approved
- PJSIP 2.17 exact git tag resolves to commit `6852b24c0d07219a06130ae982320942241eee49`; shallow clone checked out source commit `5a457451fa2712ba18e12b01738e8ff3af2b26fd` from release ref.
- `pjsip/include/pjsua2/media.hpp` defines `AudioMediaPort.createPort`, `onFrameRequested` (supply frame), and `onFrameReceived` (consume frame). `media.cpp` routes both callbacks via conference bridge. This verifies API exists in source only, not an Android app build or call.
- `COPYING` is GNU GPL v2. No product/license decision exists; no code copied into repo or APK.
- Android project has no SDK `cmdline-tools` or NDK; PJSIP `configure-android` requires NDK. No buildable AAR/JNI output in machine caches.
- Alternative artifact discovery: Maven Central `org.webrtc/google-webrtc` guessed coordinate returned 404; Google Maven metadata coordinate also 404; search.maven.org timed out after 20s. No approved alternative SDK identified.
- ADB has no device or mDNS service after server restart; stale historical endpoint `192.168.100.213:40363` refused connection (10061), another historical endpoint `192.168.0.51:40363` TCP test false. No retry of old pairing code.
- Decision: do not select/vendor PJSIP or another SDK until legal/product owner accepts GPLv2 terms or identifies alternate SDK, and until NDK + peer B/device are available. VT-005 remains blocked; no real call gates A-E run.

## 2026-10-17 — PJSIP Android configure success, compile blocked by make shell
- Freed C: space and moved an external NDK r26d feasibility toolchain to `D:\vt005-toolchain` (not repo). Direct compiler check passed: `aarch64-linux-android29-clang` reports Android clang 17.0.2.
- `ndk-build.cmd -n -C .../pjsip-apps/src/samples/android_sample APP_PLATFORM=android-29 APP_ABI=arm64-v8a` passed dry-run and emitted real arm64 clang/clang++/llvm-ar commands.
- PJSIP `configure-android` initially failed because Git Bash had no make; after adding NDK make to PATH, it rejected native Windows make as non-Cygwin; setting `OSTYPE=msys` bypassed that check and configure completed successfully for Android 29/arm64-v8a. Output says C compiler works, Android audio backend selected, pjsua2 library/application enabled, config files created.
- `make dep` cannot run: Git Bash has no GNU/MSYS make; NDK native make cannot read generated `/c/.../version.mak` path. No PJSIP library/JNI/AAR built. This is a shell/make environment blocker, not proof of API failure.
- Do not download more build tooling on nearly-full C; D has space but no need until owner approves further spike. No PJSIP source/binary copied into repo or APK.

## 2026-10-17 — App picker device smoke recovered
- ADB reconnected automatically: Redmi K70 model `23113RKC6C`, Android 16/API 36, transport 2. `adb devices -l` had one online device.
- Installed latest debug APK: `adb -t 2 install -r`: Success. `am start -W`: Status ok, COLD, TotalTime 2782 ms.
- UIAutomator opened the app picker and showed real launchable apps: `1.1.1.1`, `4A Settings Database Editor`, `AI Scanner`, `Authenticator`, `Browser`, `Calculator`, `Calendar`.
- Selected `Browser`; UI showed package `com.android.browser` and `Mở`. Force-stop + relaunch restored `Browser`, package, and selected app label. This verifies SharedPreferences persistence and launcher query on real Android.
- This is only app-picker/persistence evidence. `Browser` is not a VoIP peer; no background call monitoring, audio capture, injection, or VoIP gate A-E was run.

## 2026-10-17 — PJSIP core Android arm64 build proof
- On `D:\vt005-toolchain` (outside repo), created a temporary copy of PJSIP 2.17 with optional third-party codec source entries removed only in the copy; original source remained untouched.
- Used NDK r26d, CMake 4.3.2 and Ninja 1.12.1; configured CMake with Android toolchain, ABI `arm64-v8a`, API `android-29`, `BUILD_TESTING=OFF`, video/audio device disabled for the core spike, optional codecs disabled.
- CMake configure succeeded; Ninja built `pjsua2` target. Output includes `D:\vt005-toolchain\pjsip-cmake-core-build\pjsip\libpjsua2.a` (8,589,788 bytes) plus pjlib/pjmedia/pjsip static libraries. Build reached/link-completed `libpjsua2.a` after 54/55 target steps; target command exited success.
- NDK `llvm-nm -C` confirms symbols in `libpjsua2.a`: `pj::AudioMediaPort::createPort`, `onFrameRequested`, `onFrameReceived`, constructor/destructor/vtable. This proves native media-hook code can compile for Android arm64 in the external spike.
- This is not product integration: no JNI wrapper/AAR, no APK link, no SIP signaling endpoint, no peer B, no device call, no gates A–E. PJSIP `COPYING` is GPLv2 and product/license approval is still required before vendoring/linking.
- No PJSIP source, static library, NDK, or external build output was added to repo. Goal remains active; VT-005 not Done.

## 2026-10-17 — Completion audit update
- `python -m unittest discover -s research/models -p test_*.py -v` outside sandbox: PASS 12/12. In-sandbox run previously failed only during tempfile cleanup with WinError 5; no assertion failure.
- `python -m unittest discover -s research/audio_route -p test_*.py -v`: PASS 13/13. Backend smoke/repo check PASS.
- Latest Android `assembleDebug + lintDebug`: PASS 48 tasks. Only known `Modifier.menuAnchor()` deprecation warnings.
- Redmi K70 remains online, model `23113RKC6C`, Android 16/API 36. Relaunch audit showed persisted app `Browser` / `com.android.browser` and persisted A/B language values. This is real setup/persistence evidence only.
- Native PJSIP spike outside repo: CMake/Ninja produced Android arm64 static `libpjsua2.a`; `llvm-nm` confirmed AudioMediaPort frame hooks. No APK/JNI integration due GPLv2 decision, missing signaling/peer B and no gate A–E evidence.
- Goal remains active. Full application completion is not proven: no controlled VoIP call, no outbound/inbound replacement, no ASR/NMT/TTS inference benchmark, no duplex latency/voice evidence. Do not mark VT-005/002/004/014/030/032/033 Done.
