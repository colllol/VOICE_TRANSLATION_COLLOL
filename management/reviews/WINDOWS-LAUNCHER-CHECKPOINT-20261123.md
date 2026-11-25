# Windows launcher 0.2.1

- Branch `dev-computer`. Checkpoint W-06. Source changes are in the working tree.
- Built `packageReleaseExe` with the embedded Python backend. The installed launcher starts it on loopback if the project backend is absent, waits for health, and reads settings. Shutdown uses the child process's private stdin pipe. A pre-existing backend is reused and stays running when the app closes.
- Gradle tests passed and pytest reported 63 server tests passed. Extracted the MSI embedded in the installer into a scratch directory and exercised the real GUI launcher with temporary SQLite databases and isolated ports. Both automatic start and shutdown and reuse of an existing backend passed.
- Artifact `computer-desktop/build/compose/binaries/main-release/exe/VoiceTranslationComputer-0.2.1.exe`, 73,861,632 bytes. SHA-256 `5af96ac4e4794723703a55dae4a6248bcd0863493ba2bc1a18c48ba2e19c7a69`.
- Still awaiting normal installer acceptance and real mic, speaker and VoIP testing. Next Windows audio step is to pass complete utterances to the speech provider and connect Windows audio capture and playback.
- The project vault was unavailable at its configured path. Checkpoint retained locally.
