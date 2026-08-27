package com.example.campusai.ui.navigation

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PredictiveBackContractTest {
    @Test
    fun mainActivityOptsIntoPredictiveBack() {
        val manifest = projectFile("app/src/main/AndroidManifest.xml").readText()
        val mainActivity = Regex(
            """<activity\s+[\s\S]*?android:name="\.MainActivity"[\s\S]*?</activity>""",
        ).find(manifest)?.value.orEmpty()

        assertTrue(
            "MainActivity must opt in to the platform predictive-back callback",
            mainActivity.contains("android:enableOnBackInvokedCallback=\"true\""),
        )
    }

    @Test
    fun navigationComposeIncludesStablePredictiveBackFixes() {
        val catalog = projectFile("gradle/libs.versions.toml").readText()
        val appBuild = projectFile("app/build.gradle.kts").readText()
        val version = Regex("""navigationCompose\s*=\s*"([^"]+)"""")
            .find(catalog)
            ?.groupValues
            ?.get(1)

        assertEquals("2.9.8", version)
        assertTrue(appBuild.contains("compileSdk = 35"))
    }

    private fun projectFile(relativePath: String): File {
        val roots = generateSequence(File(System.getProperty("user.dir"))) { it.parentFile }
            .take(5)
            .toList()
        val candidates = roots.flatMap { root ->
            listOf(File(root, relativePath), File(File(root, "android"), relativePath))
        }
        return requireNotNull(candidates.firstOrNull(File::isFile)) {
            "Unable to locate Android project file: $relativePath"
        }
    }
}
