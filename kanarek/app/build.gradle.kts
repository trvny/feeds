import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
}

android {
    namespace = "com.kanarek"
    compileSdk = 37

    defaultConfig {
        applicationId = "com.kanarek"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
    }

    signingConfigs {
        create("release") {
            // Fed from CI secrets via env vars. Absent locally and on the F-Droid
            // buildserver — in that case the release build is left unsigned and the
            // consumer (F-Droid) signs it with its own key. These must stay optional:
            // requiring them would break the reproducible/F-Droid build.
            System.getenv("KEYSTORE_FILE")?.let { path ->
                storeFile = file(path)
                storePassword = System.getenv("KEYSTORE_PASSWORD")
                keyAlias = System.getenv("KEY_ALIAS")
                keyPassword = System.getenv("KEY_PASSWORD")
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            // Sign only when the keystore env is present (CI with secrets). Otherwise
            // stay unsigned so F-Droid / a downstream signer can sign the artifact.
            signingConfig = System.getenv("KEYSTORE_FILE")
                ?.let { signingConfigs.getByName("release") }
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
    }

    // `play` bundles Google Cast (Play Services — proprietary); `foss` is GMS-free and is the
    // flavor F-Droid must build. Cast code is isolated behind src/{play,foss}/…/cast/ twins
    // (CastGlue, CastButton) with identical surfaces, so main sources stay flavor-agnostic.
    flavorDimensions += "dist"
    productFlavors {
        create("play") {
            dimension = "dist"
            isDefault = true
        }
        create("foss") {
            dimension = "dist"
        }
    }

    lint {
        // Errors still fail the build; the 17 pre-existing warnings are grandfathered via
        // the checked-in baseline. Regenerate with `./gradlew updateLintBaseline` when the
        // set of known warnings changes. New (non-baselined) issues still fail CI.
        baseline = file("lint-baseline.xml")
    }
}

// Opt out of AGP 9 built-in Kotlin (see gradle.properties) so the Kotlin compiler and the
// Compose compiler stay pinned together at the catalog's `kotlin` version.
kotlin {
    compilerOptions {
        jvmTarget = JvmTarget.JVM_17
        freeCompilerArgs.add("-opt-in=androidx.compose.material3.ExperimentalMaterial3Api")
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    debugImplementation(libs.androidx.ui.tooling)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.coil.compose)

    // Player (radio/IPTV): ExoPlayer + DASH/HLS extractors + MediaSession for background
    // playback with system notification / lock-screen controls. DASH is required by several
    // bundled TVP/Plus streams (.mpd); without it DefaultMediaSourceFactory throws
    // ClassNotFoundException (DashMediaSource$Factory) on prepare().
    implementation(libs.androidx.media3.exoplayer)
    implementation(libs.androidx.media3.exoplayer.dash)
    implementation(libs.androidx.media3.exoplayer.hls)
    implementation(libs.androidx.media3.session)

    // Google Cast sender (play flavor only — proprietary GMS, must never leak into foss):
    // media3-cast bridges CastPlayer onto the Player interface; mediarouter powers the in-app
    // Compose device picker; cast-framework is the session machinery + OptionsProvider.
    "playImplementation"(libs.androidx.media3.cast)
    "playImplementation"(libs.androidx.mediarouter)
    "playImplementation"(libs.play.services.cast.framework)

    testImplementation(libs.junit)
}
