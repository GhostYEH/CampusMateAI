package com.example.campusai.ui.screens.focus

internal enum class FocusPrimarySlot {
    PAUSE_RESUME,
    TIMER,
    FINISH,
}

internal enum class FocusStageLayout {
    PORTRAIT,
    LANDSCAPE;

    val primarySlots: List<FocusPrimarySlot>
        get() = listOf(
            FocusPrimarySlot.PAUSE_RESUME,
            FocusPrimarySlot.TIMER,
            FocusPrimarySlot.FINISH,
        )
}

internal fun focusStageLayout(maxWidthDp: Int, maxHeightDp: Int): FocusStageLayout =
    if (maxWidthDp > maxHeightDp) FocusStageLayout.LANDSCAPE else FocusStageLayout.PORTRAIT
