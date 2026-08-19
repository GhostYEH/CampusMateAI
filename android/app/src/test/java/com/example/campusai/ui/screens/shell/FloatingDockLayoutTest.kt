package com.example.campusai.ui.screens.shell

import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Test

class FloatingDockLayoutTest {
    @Test
    fun scrollableContentReservesSystemNavigationAndFloatingDockSpace() {
        assertEquals(116.dp, floatingDockContentBottomPadding(navigationBarHeight = 24.dp))
    }
}
