import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.jetbrains.kotlin.android)
    alias(libs.plugins.jetbrains.kotlin.compose)
    id("org.jetbrains.kotlin.kapt")
}

kotlin {
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}

android {
    namespace = "com.example.campusai"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.campusai"
        minSdk = 28
        targetSdk = 34
        versionCode = 1
        versionName = "1.0"

        val localProperties = Properties().apply {
            val file = rootProject.file("local.properties")
            if (file.exists()) file.inputStream().use(::load)
        }
        // Command-line/project properties take priority. local.properties gives
        // physical devices a safe, untracked place to use the computer's LAN IP.
        val configuredApiBaseUrl = (project.findProperty("API_BASE_URL") as String?)
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: localProperties.getProperty("API_BASE_URL")
                ?.trim()
                ?.takeIf { it.isNotEmpty() }
            ?: "http://10.0.2.2:8000/api/v1/"
        val normalizedApiBaseUrl = if (configuredApiBaseUrl.endsWith("/")) {
            configuredApiBaseUrl
        } else {
            "$configuredApiBaseUrl/"
        }
        buildConfigField("String", "API_BASE_URL", "\"$normalizedApiBaseUrl\"")

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables {
            useSupportLibrary = true
        }
    }

    buildTypes {
        debug {
            buildConfigField("boolean", "DEFAULT_USE_MOCK", "false")
        }
        release {
            buildConfigField("boolean", "DEFAULT_USE_MOCK", "false")
            buildConfigField("String", "API_BASE_URL", "\"https://api.campusmate.example.com/api/v1/\"")
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
        create("demo") {
            initWith(getByName("release"))
            signingConfig = signingConfigs.getByName("debug")
            isMinifyEnabled = false
            isShrinkResources = false
            buildConfigField("boolean", "DEFAULT_USE_MOCK", "false")
            matchingFallbacks += listOf("release")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    buildFeatures {
        compose = true
        buildConfig = true
    }
    androidResources {
        // ExpressionModelRunner maps the model with AssetManager.openFd().
        // Keep the FlatBuffer uncompressed so openFd() can obtain an offset/length.
        noCompress += "tflite"
    }
    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation("com.microsoft.onnxruntime:onnxruntime-android:1.24.3")
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.media3.exoplayer)
    implementation(libs.androidx.media3.ui)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.moshi)
    implementation(libs.retrofit.converter.scalars)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.moshi)
    implementation(libs.moshi.kotlin)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.security.crypto)
    implementation(libs.coil.compose)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(libs.google.ai.edge.litert)
    implementation(libs.google.mlkit.face.detection)
    implementation(libs.tensorflow.lite.task.vision) {
        // The app already provides LiteRT 1.4.2 for expression inference.
        // Task Vision's legacy TFLite API is binary-compatible, so avoid
        // packaging its second runtime with the same org.tensorflow.lite classes.
        exclude(group = "org.tensorflow", module = "tensorflow-lite-api")
    }
    implementation("com.google.mlkit:barcode-scanning:17.3.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-play-services:1.8.1")
    implementation(libs.androidx.room.runtime)
    implementation(libs.androidx.room.ktx)
    kapt(libs.androidx.room.compiler)
    testImplementation(libs.junit)
    testImplementation("org.mockito:mockito-core:5.12.0")
    testImplementation("androidx.test:core-ktx:1.5.0")
    testImplementation("androidx.test.ext:junit:1.1.5")
    testImplementation("androidx.work:work-testing:2.9.0")
    testImplementation("org.robolectric:robolectric:4.11.1")
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
    androidTestImplementation(libs.androidx.ui.test.junit4)
    debugImplementation(libs.androidx.ui.tooling)
    debugImplementation(libs.androidx.ui.test.manifest)
}

kapt {
    correctErrorTypes = true
}
