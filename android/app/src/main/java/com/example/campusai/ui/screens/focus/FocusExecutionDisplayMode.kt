package com.example.campusai.ui.screens.focus

/** Display layer for an active session; it does not change the selected focus experience. */
internal object FocusExecutionDisplayMode {
    const val IMMERSIVE = "immersive"
    const val STANDARD = "standard"
    const val DEFAULT = IMMERSIVE

    fun toggled(mode: String): String = when (mode) {
        IMMERSIVE -> STANDARD
        else -> IMMERSIVE
    }
}
