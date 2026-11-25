# Windows installer 0.2.4 checkpoint

W-06 · Branch `dev-computer`. Scope was limited to `computer-desktop/build.gradle.kts`, `computer-desktop/README.md`, and this checkpoint. The repository was already dirty in unrelated desktop/backend/audio files; no unrelated files were changed. The configured vault path `C:/Users/Admin/Documents/Codex Knowledge` was unavailable, so this checkpoint is local and not vault-synced.

## Build

Prerequisites verified:

- Java: Eclipse Temurin 21.0.11 LTS.
- Gradle wrapper: `computer-desktop/gradlew`.
- Build Python: `C:/Users/Admin/AppData/Local/hermes/installs/902a4fe5d10abbac/environments/04a071d1f1514a349c7d751efee8af1b/venv/Scripts/python.exe`.
- PyInstaller: 6.22.3 in that environment. The shell-default Python did not contain PyInstaller, so Gradle now accepts `-PpythonExecutable` or `PYTHON`.

Command:

```text
./gradlew test packageReleaseExe packageReleaseMsi -PpythonExecutable=C:/Users/Admin/AppData/Local/hermes/installs/902a4fe5d10abbac/environments/04a071d1f1514a349c7d751efee8af1b/venv/Scripts/python.exe --rerun-tasks --console=plain
```

Result: exit `0`; `BUILD SUCCESSFUL in 4m 12s`; 17 actionable tasks executed. The build ran Gradle tests, PyInstaller backend packaging, EXE packaging, and MSI packaging. Gradle emitted duplicate-class/resource notes from the existing dependency set; they did not fail the build.

Artifacts:

- EXE: `D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL/computer-desktop/build/compose/binaries/0.2.4/main-release/exe/VoiceTranslationComputer-0.2.4.exe`
  - Size: `73890304` bytes
  - SHA-256: `b00cf2be313e7f69fad9b526cd7b5bbe597dedfa939f9790a56879b1f05ac89d`
- MSI: `D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL/computer-desktop/build/compose/binaries/0.2.4/main-release/msi/VoiceTranslationComputer-0.2.4.msi`
  - Size: `73206649` bytes
  - SHA-256: `5f80f566cd499d4d6f577228d957680f1c990082e551f71b9c574fbccae5e363`

The EXE embedded MSI was extracted with the existing Windows probe. MSI `ProductVersion` read back as `0.2.4`; administrative extraction returned `0` and contained the launcher, bundled JVM, and `VoiceTranslationBackend.exe`.

## Isolated runtime smoke

Command:

```text
python C:/Users/Admin/AppData/Local/hermes/cache/scratch/vt023_window_probe.py D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL/computer-desktop/build/compose/binaries/0.2.4/main-release/exe/VoiceTranslationComputer-0.2.4.exe
```

Result: pass. The extracted launcher started a visible `Voice Translation — Operator` window owned by child PID `8560`; the bundled backend returned `/health` HTTP `200` on isolated port `64129`; an isolated SQLite database was created; `WM_CLOSE` returned launcher exit `0`; owned descendants were gone and the port was released. No production database or shared backend was used.

This proves packaged GUI startup and local backend health only. It does not prove physical microphone/speaker quality, Azure, VoIP, SIP, outbound-track injection, or the unfinished native/baresip bridge.

## Installed-product preservation and lifecycle

Before lifecycle testing, registry and filesystem inspection read:

- Installed display version: `0.2.3`.
- Installed location: `D:/0.2.3/`.
- Registry uninstall entry: `{C4D12515-C695-39CB-911E-1DB28BFED941}`.
- User data: `C:/Users/Admin/AppData/Local/VoiceTranslationComputer/computer-data.db`.
- Database size: `20480` bytes.
- Database SHA-256 before upgrade: `c761787a7ebc412ba86201452160894278b53472cc44e3b5d2dce836793174c8`.
- Three `VoiceTranslationComputer-0.2.2.exe` processes were present. They were not stopped; no `VoiceTranslationBackend.exe` was running before the upgrade.

### Diagnosis

The earlier exit code `83` was not a Windows Installer return code. The saved verbose logs show `msiexec` received a `D:/...` package path. Its elevated server-side process interpreted that as `/Documents/...` and failed with MSI note `1314` before opening the package. This was path conversion at the MSYS/Bash boundary, not evidence that the MSI was invalid.

The MSI was copied byte-for-byte to `C:/Users/Admin/AppData/Local/hermes/cache/scratch/VoiceTranslationComputer-0.2.4.msi` and invoked through Python `subprocess` with a native Windows path. The first non-elevated attempt returned `1603`; its full log identifies error `1730` during `InstallInitialize`: the all-users 0.2.3 product requires Administrator rights to remove. No product state changed on that attempt.

### Upgrade

The same MSI was launched with the Windows `runas` verb (UAC elevation, no credentials supplied to the tool):

```text
msiexec /i "C:\Users\Admin\AppData\Local\hermes\cache\scratch\VoiceTranslationComputer-0.2.4.msi" /qn /norestart /L*v "...\vt024-upgrade-elevated.log"
```

Result: MSI exit/status `0`. The log identifies old ProductCode `{C4D12515-C695-39CB-911E-1DB28BFED941}` and new ProductCode `{25809A21-A420-3DD5-8FE1-DD158D34EAF7}`, ProductVersion `0.2.4`. The install location changed from `D:/0.2.3/` to `C:/Program Files/VoiceTranslationComputer/` in this environment. The user DB SHA-256 remained unchanged.

The installed `VoiceTranslationComputer.exe` was launched from Program Files. Its process and bundled `VoiceTranslationBackend.exe` appeared, and `http://127.0.0.1:8765/health` returned HTTP `200` with `{"status":"ok","service":"voice-translation-computer"}`.

### Uninstall and reinstall

Before uninstall, the 20,480-byte user DB was copied to scratch at `C:/Users/Admin/AppData/Local/hermes/cache/scratch/computer-data-before-uninstall.db`; the backup hash matched the original. Elevated MSI uninstall of ProductCode `{25809A21-A420-3DD5-8FE1-DD158D34EAF7}` completed with status `0`, MSI exit `3010` (success; restart required/deferred). Restart Manager restarted the app during removal. After its processes exited naturally, the bundled backend port was closed and the user DB hash still matched the original.

The same MSI was then reinstalled with elevation. MSI status was `0`; registry read-back reported version `0.2.4` and location `C:/Program Files/VoiceTranslationComputer/`. A fresh launch again produced the app and bundled backend processes, and `/health` returned HTTP `200`. Final user DB size/hash remained `20480` / `c761787a7ebc412ba86201452160894278b53472cc44e3b5d2dce836793174c8`.

The existing `0.2.2` processes were left untouched throughout. The final `0.2.4` GUI/backend processes were also left running. The uninstall log requests a reboot (status `3010`); it was deferred with `/norestart` and no reboot was performed.

### Artifact read-back

- EXE: `D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL/computer-desktop/build/compose/binaries/0.2.4/main-release/exe/VoiceTranslationComputer-0.2.4.exe`; `73890304` bytes; SHA-256 `b00cf2be313e7f69fad9b526cd7b5bbe597dedfa939f9790a56879b1f05ac89d`.
- MSI: `D:/Documents/GitHub/VOICE_TRANSLATION_COLLOL/computer-desktop/build/compose/binaries/0.2.4/main-release/msi/VoiceTranslationComputer-0.2.4.msi`; `73206649` bytes; SHA-256 `5f80f566cd499d4d6f577228d957680f1c990082e551f71b9c574fbccae5e363`.

Upgrade, uninstall, reinstall, installed registry read-back, and runtime health are verified on this machine. This does not verify physical microphone/speaker quality, Azure, VoIP, SIP, outbound-track injection, or the unfinished native/baresip bridge. Vault path `C:/Users/Admin/Documents/Codex Knowledge` was unavailable, so this checkpoint is local and not vault-synced.
## Changes and limits

`build.gradle.kts` now sets version `0.2.4`, keeps versioned Compose output directories, and supports an explicit Python executable for PyInstaller. `README.md` documents the `0.2.4` package name, lifecycle/cancellation caveat, fake local mic/speaker scope, and the absence of desktop SIP/baresip integration. The release does not package unfinished `research/audio_route` work.

No commit was created, per task instruction. A separate reviewer is still required before any release status changes.
