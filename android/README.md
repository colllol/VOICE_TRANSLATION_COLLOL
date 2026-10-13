# Android scaffold

Requirements: JDK 21, Android SDK platform 36/build-tools 36.0.0. Set ANDROID_HOME to your SDK.

Windows: `android\gradlew.bat -p android :app:assembleDebug :app:lintDebug`
Linux: `bash android/gradlew -p android :app:assembleDebug :app:lintDebug`

APK: `android/app/build/outputs/apk/debug/app-debug.apk`.
This app displays a development status screen only. Audio capture and VoIP integration are separate tickets.
