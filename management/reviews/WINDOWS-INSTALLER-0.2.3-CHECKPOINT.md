# Windows installer 0.2.3

W-06 · Branch `dev-computer`. Windows Installer recorded error `1638` on repeated attempts to install a rebuilt `0.2.2` over an existing `0.2.2`. Changed the package version to `0.2.3` and separated the Gradle output directory by version because the running `0.2.2` installer locked the old output. This release is for offline `fake` mode. Backend suite reported 64 passed.

`./gradlew test packageReleaseExe --console=plain` succeeded. Installer `computer-desktop/build/compose/binaries/0.2.3/main-release/exe/VoiceTranslationComputer-0.2.3.exe`, 88,748,544 bytes, SHA-256 `aeeb8436d56bd03cd71281a114e7ac92e18e1e91c49627dbc1f8d1414156998e`. The embedded MSI reports `ProductVersion=0.2.3`. Administrative extraction confirmed the launcher and bundled JVM and backend. Vault unavailable during this attempt.

Extracted GUI smoke passed on repeat verification: the original probe looked only at the launcher PID and missed the Operator window owned by a same-name child. In the repeat run, launcher PID 23024 spawned GUI PID 16036, whose Operator window was visible at 4.29 s. The isolated backend returned `/health` HTTP 200 at 6.05 s and created the scratch DB. `WM_CLOSE` yielded launcher exit 0, no remaining tracked descendants, and port 58195 was released. Normal install, upgrade, and uninstall are not verified. This artifact predates the session lifecycle changes.
