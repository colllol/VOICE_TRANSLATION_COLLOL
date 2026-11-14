plugins {
    id("org.jetbrains.kotlin.jvm") version "2.2.10"
    id("org.jetbrains.compose") version "1.9.0"
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10"
}

group = "com.collol.voicetranslation"
version = "0.1.0"

kotlin { jvmToolchain(21) }

dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    testImplementation(kotlin("test"))
}

compose.desktop {
    application {
        mainClass = "com.collol.voicetranslation.desktop.MainKt"
        nativeDistributions { targetFormats(org.jetbrains.compose.desktop.application.dsl.TargetFormat.Exe, org.jetbrains.compose.desktop.application.dsl.TargetFormat.Msi) }
    }
}

tasks.test { useJUnitPlatform() }
