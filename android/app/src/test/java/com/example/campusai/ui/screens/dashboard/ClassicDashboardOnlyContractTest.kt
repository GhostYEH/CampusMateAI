package com.example.campusai.ui.screens.dashboard

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassicDashboardOnlyContractTest {
    @Test
    fun androidHomeKeepsOnlyTheClassicDashboard() {
        val dashboardScreen = source("ui/screens/dashboard/DashboardScreen.kt").readText()
        val dataStore = source("data/local/AppDataStore.kt").readText()
        val repository = source("data/repository/AppRepository.kt").readText()
        val settings = source("ui/screens/profile/SettingsScreen.kt").readText()

        assertTrue(dashboardScreen.contains("ClassicDashboardScreen(repository, onNavigate)"))
        assertFalse(dashboardScreen.contains("ImmersiveDashboardScreen"))
        assertFalse(dashboardScreen.contains("DashboardStyle"))
        assertFalse(dataStore.contains("KEY_DASHBOARD_STYLE"))
        assertFalse(repository.contains("dashboardStyle"))
        assertFalse(settings.contains("DashboardStyleSelector"))
        assertFalse(source("ui/screens/dashboard/ImmersiveDashboardScreen.kt").exists())
        assertFalse(source("ui/screens/dashboard/ImmersiveDashboardSpec.kt").exists())
    }

    private fun source(relativePath: String): File {
        val candidates = listOf(
            File("src/main/java/com/example/campusai", relativePath),
            File("app/src/main/java/com/example/campusai", relativePath),
        )
        return candidates.firstOrNull { it.exists() } ?: candidates.first()
    }
}
