package com.example.campusai.ui.screens.shell

import org.junit.Assert.assertEquals
import org.junit.Test

class LiquidGlassDockDragTest {
    @Test
    fun dragOffsetIsClampedToTheFirstAndLastItems() {
        assertEquals(
            -200f,
            clampDockDragOffset(
                selectedIndex = 2,
                itemCount = 5,
                itemWidthPx = 100f,
                requestedOffsetPx = -500f,
            ),
        )
        assertEquals(
            200f,
            clampDockDragOffset(
                selectedIndex = 2,
                itemCount = 5,
                itemWidthPx = 100f,
                requestedOffsetPx = 500f,
            ),
        )
    }

    @Test
    fun releaseSnapsToTheNearestItemCenter() {
        assertEquals(2, dockDragTargetIndex(2, 49f, 100f, 5))
        assertEquals(3, dockDragTargetIndex(2, 51f, 100f, 5))
        assertEquals(0, dockDragTargetIndex(2, -500f, 100f, 5))
        assertEquals(4, dockDragTargetIndex(2, 500f, 100f, 5))
    }

    @Test
    fun invalidGeometryKeepsTheCurrentSelectionStable() {
        assertEquals(2, dockDragTargetIndex(2, 80f, 0f, 5))
        assertEquals(0f, clampDockDragOffset(2, 0, 100f, 80f))
    }
}
