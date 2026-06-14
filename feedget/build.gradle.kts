// Top-level build file. Plugin versions come from gradle/libs.versions.toml.
// AGP 9 provides built-in Kotlin, so no Kotlin or Compose compiler plugin is declared here.
plugins {
    alias(libs.plugins.android.application) apply false
}
