package com.example.campusai.features.gamification

import org.junit.Assert.assertEquals
import org.junit.Test

class DashboardStyleTest {
    @Test
    fun unknownOrMissingPreferenceFallsBackToClassic() {
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue(null))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue(""))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("arcade"))
    }

    @Test
    fun gamifiedPreferenceRoundTripsWithoutDependingOnEnumCase() {
        assertEquals("gamified", DashboardStyle.GAMIFIED.storedValue)
        assertEquals(DashboardStyle.GAMIFIED, DashboardStyle.fromStoredValue("gamified"))
        assertEquals(DashboardStyle.GAMIFIED, DashboardStyle.fromStoredValue("GAMIFIED"))
    }

    @Test
    fun immersivePreferenceRoundTripsWithoutDependingOnEnumCase() {
        assertEquals("immersive", DashboardStyle.IMMERSIVE.storedValue)
        assertEquals(DashboardStyle.IMMERSIVE, DashboardStyle.fromStoredValue("immersive"))
        assertEquals(DashboardStyle.IMMERSIVE, DashboardStyle.fromStoredValue("IMMERSIVE"))
    }
}
