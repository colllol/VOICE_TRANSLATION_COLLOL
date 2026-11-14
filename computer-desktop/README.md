# Windows operator app

Kotlin/JVM + Compose Multiplatform desktop shell for the replacement backend. The UI is intentionally an operator console: it controls the A-side session and reports backend state. It does not claim arbitrary-app call interception.

## Build

Run from this directory with the Gradle wrapper copied from the Android project or a compatible Gradle installation:

```text
gradle test
# later: gradle run
# later: gradle packageReleaseExe packageReleaseMsi
```
