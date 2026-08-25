package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduConnectionDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class EduAllowedOriginsContractTest {
    @Test
    fun backendResponseDeserializesAllowedOrigins() {
        val adapter = Moshi.Builder()
            .addLast(KotlinJsonAdapterFactory())
            .build()
            .adapter(EduConnectionDto::class.java)

        val connection = requireNotNull(
            adapter.fromJson(
                """{"id":"connection-1","state":"waiting_user_login","provider":"zhengfang","allowed_origins":["https://sso.huel.edu.cn"]}""",
            ),
        )

        assertEquals(listOf("https://sso.huel.edu.cn"), connection.allowed_origins)
    }

    @Test
    fun productionNavigationForwardsBackendAllowedOriginsToLoginScreen() {
        val eduSystemSource = productionSource(
            "com/example/campusai/ui/screens/profile/EduSystemScreen.kt",
        )
        val navHostSource = productionSource(
            "com/example/campusai/ui/navigation/AppNavHost.kt",
        )

        assertTrue(eduSystemSource.contains("waiting.connection.allowed_origins"))
        assertTrue(navHostSource.contains("allowedOrigins.joinToString"))
        assertTrue(navHostSource.contains("backendAllowedOrigins = allowedOrigins"))
    }

    private fun productionSource(relativePath: String): String {
        val candidates = listOf(
            File("src/main/java", relativePath),
            File("app/src/main/java", relativePath),
        )
        return requireNotNull(candidates.firstOrNull(File::isFile)) {
            "Unable to locate production source: $relativePath"
        }.readText()
    }
}
