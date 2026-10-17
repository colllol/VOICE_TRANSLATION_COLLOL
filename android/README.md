# Android scaffold

Requirements: JDK 21, Android SDK platform 36/build-tools 36.0.0. Set ANDROID_HOME to your SDK.

Windows: `android\gradlew.bat -p android :app:assembleDebug :app:lintDebug`
Linux: `bash android/gradlew -p android :app:assembleDebug :app:lintDebug`

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
The VT-023 preview provides language selection, swap, a fail-closed readiness check, and Close. It does not capture audio, connect calls, or translate. Language choices survive activity recreation, not durable storage. Audio capture and VoIP integration remain separate gated tickets.
