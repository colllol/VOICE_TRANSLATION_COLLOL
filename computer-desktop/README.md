# Windows operator app

Kotlin/JVM + Compose Multiplatform app for the A-side operator. This build supports a local microphone-to-speaker test in each language direction. It does not connect to a VoIP call.

## Build

Run from this directory with the Gradle wrapper copied from the Android project or a compatible Gradle installation:

```text
./gradlew test
./gradlew run
./gradlew packageReleaseExe packageReleaseMsi
```

## Run on Windows

Install `VoiceTranslationComputer-0.2.4.exe`, then open Voice Translation Computer. The installed launcher starts the bundled backend and loads settings automatically. If it finds a healthy Voice Translation backend on `127.0.0.1:8765`, it reuses that process. Closing the app shuts down the backend it started. Close any independently running older backend normally before testing the new audio path; the app will not stop it for you.

The bundled backend writes settings and logs to `%LOCALAPPDATA%\VoiceTranslationComputer`. A manually launched backend can use a separate SQLite file. To point an app-owned backend at an existing database, set `VOICE_TRANSLATION_DB_PATH` to its absolute path before launching the app.

On the Windows build machine, install `computer/requirements.txt` and `pyinstaller==6.22.3` into the Python environment used by Gradle. The build accepts `-PpythonExecutable=C:/path/to/python.exe` or the `PYTHON` environment variable when `python` is not the intended interpreter. Users of the installer do not need Python or a JDK.

## Run the development backend

From the repository root, install `computer/requirements.txt` in your Python environment, then run:

```text
python -m computer.server
```

The Windows app's **Check backend** action checks `http://127.0.0.1:8765/health`.
**Start session** opens a WebSocket session and shows the backend-issued ID. **Stop session** sends a cancellation request. Run `python -m computer.server.desktop_smoke` from the repository root with `COMPUTER_TRANSLATION_PROVIDER=fake` to exercise both directions and session controls against a temporary backend and database.

## Test voice on the laptop

**Keep 0.2.2, 0.2.3, and 0.2.4 in offline `fake` mode for this release check.** The lifecycle changes cancel the desktop session and wait for its audio job, but an in-flight synchronous Azure request cannot be forcibly interrupted. The Azure steps below are not installer acceptance evidence.

1. Select the default microphone and speakers in Windows, and enable microphone access for desktop apps. Start a session.
2. Click **Test mic: vi → en**, then speak a short sentence during the four-second recording. Repeat with **Test mic: en → vi**. The default `fake` provider plays a tone for each direction. A tone verifies the local audio workflow but not recognition or intelligibility, and can play even if the microphone captured silence.
3. For live translation, set `COMPUTER_TRANSLATION_PROVIDER=azure`, `COMPUTER_AZURE_SPEECH_REGION`, `COMPUTER_AZURE_SPEECH_KEY`, `COMPUTER_AZURE_TRANSLATOR_KEY`, and `COMPUTER_AZURE_TRANSLATOR_REGION` (omit the latter for a global resource) in the launching process environment. Restart the app and its owned backend; a reused backend retains its own environment. Verify the UI shows Azure before recording. Never paste keys into logs or chat.
4. Repeat both directions with Azure. Pass when the speaker plays understandable translated speech in the target language for both tests. Azure receives audio and text for processing; use non-sensitive test phrases. Record pass/fail and the app status only, without audio, credentials, or transcripts.

The test sends 20 ms PCM chunks over loopback, then translates the whole utterance after recording stops. It does not stream translation while you speak, preserve speaker identity, or exercise a real call. This release does not package the unfinished native/baresip bridge and does not claim desktop SIP or outbound-track injection. See the [roadmap](../management/ROADMAP.md) for the remaining gates.
