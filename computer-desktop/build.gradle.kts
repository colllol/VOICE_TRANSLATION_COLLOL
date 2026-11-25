import org.jetbrains.compose.desktop.application.dsl.TargetFormat

plugins {
    id("org.jetbrains.kotlin.jvm") version "2.2.10"
    id("org.jetbrains.compose") version "1.9.0"
    id("org.jetbrains.kotlin.plugin.compose") version "2.2.10"
}

group = "com.collol.voicetranslation"
version = "0.2.5"
val backendResources = layout.buildDirectory.dir("generated/desktop-resources")
val pythonExecutable = providers.gradleProperty("pythonExecutable")
    .orElse(providers.environmentVariable("PYTHON"))
    .orElse("python")

kotlin { jvmToolchain(21) }

dependencies {
    implementation(compose.desktop.currentOs)
    implementation(compose.material3)
    implementation("com.google.code.gson:gson:2.13.2")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
    testImplementation(kotlin("test"))
}

compose.desktop {
    application {
        mainClass = "com.collol.voicetranslation.desktop.MainKt"
        nativeDistributions {
            modules("java.net.http", "java.desktop")
            targetFormats(TargetFormat.Exe, TargetFormat.Msi)
            appResourcesRootDir.set(backendResources)
            outputBaseDir.set(layout.buildDirectory.dir("compose/binaries/${project.version}"))
        }
    }
}

tasks.test { useJUnitPlatform() }

val packagePythonBackend by tasks.registering(Exec::class) {
    val outputDir = backendResources.map { it.dir("windows/backend") }
    inputs.files(fileTree("../computer") { include("**/*.py", "requirements.txt") })
    outputs.dir(outputDir)
    doFirst { outputDir.get().asFile.mkdirs() }
    commandLine(
        pythonExecutable.get(), "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
        "--name", "VoiceTranslationBackend", "--distpath", outputDir.get().asFile.absolutePath,
        "--workpath", layout.buildDirectory.dir("pyinstaller-work").get().asFile.absolutePath,
        "--specpath", layout.buildDirectory.dir("pyinstaller-spec").get().asFile.absolutePath,
        "--collect-all", "uvicorn", "--collect-all", "websockets", "--collect-all", "pydantic_core",
        "--hidden-import", "uvicorn.logging", "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto", "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--paths", project.projectDir.parentFile.absolutePath,
        "${project.projectDir.parentFile.absolutePath}/computer/server/__main__.py",
    )
    workingDir = project.projectDir.parentFile
}

tasks.matching { it.name == "prepareAppResources" }.configureEach {
    if (System.getProperty("os.name").startsWith("Windows")) dependsOn(packagePythonBackend)
}
