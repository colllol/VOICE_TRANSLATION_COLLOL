# Android scaffold

Requirements: JDK 21, Android SDK platform 36/build-tools 36.0.0. Set ANDROID_HOME to your SDK.

Windows: `android\gradlew.bat -p android :app:assembleDebug :app:lintDebug`
Linux: `bash android/gradlew -p android :app:assembleDebug :app:lintDebug`

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
The VT-023 preview provides a picker for launchable apps on device A, language selection, swap, a fail-closed readiness check, and Close. The picker only selects and opens an app; it does not monitor background calls, capture audio, connect calls, or translate. The app list and language choices are session-only. Audio capture and controlled VoIP integration remain separate gated tickets.
