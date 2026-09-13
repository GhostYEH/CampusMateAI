package com.example.campusai.data.local

import org.junit.Assert.assertEquals
import org.junit.Test

class DashboardStyleTest {
    @Test
    fun unknownStoredValuesFallBackToClassic() {
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue(null))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue(""))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("arcade"))
    }

    @Test
    fun removedGamifiedPreferenceDegradesToClassic() {
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("gamified"))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("GAMIFIED"))
    }

    @Test
    fun storedValuesRoundTrip() {
        assertEquals("classic", DashboardStyle.CLASSIC.storedValue)
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("classic"))
        assertEquals(DashboardStyle.CLASSIC, DashboardStyle.fromStoredValue("CLASSIC"))
        assertEquals("immersive", DashboardStyle.IMMERSIVE.storedValue)
        assertEquals(DashboardStyle.IMMERSIVE, DashboardStyle.fromStoredValue("immersive"))
        assertEquals(DashboardStyle.IMMERSIVE, DashboardStyle.fromStoredValue("IMMERSIVE"))
    }
}
