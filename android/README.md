# Android scaffold

Requirements: JDK 21, Android SDK platform 36/build-tools 36.0.0. Configure the SDK with ANDROID_HOME, ANDROID_SDK_ROOT, or android/local.properties (`sdk.dir=...`).

Windows: `android\gradlew.bat -p android :app:assembleDebug :app:lintDebug`
Linux: `bash android/gradlew -p android :app:assembleDebug :app:lintDebug`

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
The VT-023 preview provides a picker for launchable apps on device A, language selection, swap, a fail-closed readiness check, and Close. The picker only selects and opens an app; it does not monitor background calls, capture audio, connect calls, or translate. The selected app package and language choices are stored locally with SharedPreferences. Audio capture and controlled VoIP integration remain separate gated tickets.

## Developer Voice Lab

Build a separate developer APK with `:app:assembleDeveloper`; its application ID is `com.collol.voicetranslation.developer`, so it can be installed alongside the debug preview. Open **Developer Voice Lab**, choose **Bắt đầu test**, and speak Vietnamese. The harness uses Android `SpeechRecognizer` for ASR, downloads the ML Kit Vietnamese-to-English model on first use, and Android TextToSpeech to play translated output. First use requires network access to fetch the translation model. ASR availability and offline behavior depend on the speech recognition service installed on the device.

The diagnostics panel reports the requested 16 kHz sample rate, PCM window count, normalized RMS/peak, dominant frequency, and per-stage elapsed time. PCM is analyzed in memory, not persisted. Diagnostics own the microphone only during model preparation; `SpeechRecognizer` starts only after the diagnostics reader thread stops and releases its `AudioRecord`, because Android audio services may reject two simultaneous microphone clients with `ERROR_CLIENT` (code 5). During ASR, the displayed RMS is derived from `RecognitionListener.onRmsChanged`. A single client-error retry is attempted after destroying the old recognizer.

The Developer screen also provides an explicit **Chạy benchmark NMT** action. It downloads or verifies the ML Kit `vi->en` model, runs one warm-up translation, then translates ten fixed Vietnamese sentences sequentially and reports successful sample count, failures, min/median/mean/p95 latency, and model-ready/download time. These are measured on the device when the action is run; no benchmark result is checked into the repository. The benchmark measures ML Kit NMT only, not ASR, TTS, VoIP, or end-to-end latency.

Transcript and translated text appear only in the developer screen. Android TextToSpeech must have an enabled system TTS engine and a Vietnamese-to-English-capable voice on the device; the harness reports a clear error when the ROM has no usable engine. Developer APK is a one-device, one-way test harness: it does not capture another app's call audio or inject translated audio into a call, and does not establish speaker preservation or the sub-second latency target.

Verify both variants:

```sh
./gradlew :app:testDeveloperUnitTest :app:assembleDeveloper :app:lintDeveloper
./gradlew :app:testDebugUnitTest :app:assembleDebug :app:lintDebug
```
