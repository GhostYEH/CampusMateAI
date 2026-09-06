package com.example.campusai.ui.screens.shell

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test

class FloatingDockLayoutTest {
    @Test
    fun scrollableContentReservesSystemNavigationAndFloatingDockSpace() {
        assertEquals(104.dp, floatingDockContentBottomPadding(navigationBarHeight = 24.dp))
    }

    @Test
    fun phoneDockUsesTheAvailableWidth() {
        assertEquals(332.dp, floatingDockWidth(availableWidth = 332.dp))
    }

    @Test
    fun largeWindowDockStopsGrowingPastItsReadableWidth() {
        assertEquals(560.dp, floatingDockWidth(availableWidth = 772.dp))
    }
}
