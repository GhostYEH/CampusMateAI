package com.example.campusai.ui.screens.focus

import org.junit.Assert.assertEquals
import org.junit.Test

class FocusStageLayoutTest {
    @Test
    fun portraitWindowKeepsTimerControlsOnOneHorizontalAxis() {
        assertEquals(
            FocusStageLayout.PORTRAIT,
            focusStageLayout(maxWidthDp = 412, maxHeightDp = 915),
        )
        assertEquals(
            listOf(FocusPrimarySlot.PAUSE_RESUME, FocusPrimarySlot.TIMER, FocusPrimarySlot.FINISH),
            FocusStageLayout.PORTRAIT.primarySlots,
        )
    }

    @Test
    fun landscapeWindowUsesWideStageWithoutChangingControlOrder() {
        assertEquals(
            FocusStageLayout.LANDSCAPE,
            focusStageLayout(maxWidthDp = 915, maxHeightDp = 412),
        )
        assertEquals(
            listOf(FocusPrimarySlot.PAUSE_RESUME, FocusPrimarySlot.TIMER, FocusPrimarySlot.FINISH),
            FocusStageLayout.LANDSCAPE.primarySlots,
        )
    }
}
