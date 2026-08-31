plugins {
    id("java")
    id("org.jetbrains.kotlin.jvm") version "2.3.20"
    id("org.jetbrains.intellij.platform") version "2.18.1"
}

group = "com.assistant"
version = "1.1.0"

repositories {
    mavenCentral()
    intellijPlatform {
        defaultRepositories()
    }
}

dependencies {
    intellijPlatform {
        // 直接用本机已安装的 IDEA 2026.2.1 作为平台,免去下载 1GB 发行版
        local("D:/AI/IntelliJ IDEA 2026.2.1")
    }
    implementation("com.google.code.gson:gson:2.10.1")
}
