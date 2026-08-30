package com.example.campusai.ui.screens.shell

internal data class LiquidGlassDockProfile(
    val blurEnabled: Boolean,
    val lensEnabled: Boolean,
    val vibrancyEnabled: Boolean,
    val blurRadiusDp: Float,
    val surfaceAlpha: Float,
)

internal fun liquidGlassDockProfile(
    apiLevel: Int,
    darkMode: Boolean,
): LiquidGlassDockProfile = when {
    apiLevel >= 33 -> LiquidGlassDockProfile(
        blurEnabled = true,
        lensEnabled = true,
        vibrancyEnabled = true,
        blurRadiusDp = 8f,
        surfaceAlpha = if (darkMode) 0.34f else 0.40f,
    )
    apiLevel >= 31 -> LiquidGlassDockProfile(
        blurEnabled = true,
        lensEnabled = false,
        vibrancyEnabled = false,
        blurRadiusDp = 12f,
        surfaceAlpha = if (darkMode) 0.46f else 0.52f,
    )
    else -> LiquidGlassDockProfile(
        blurEnabled = false,
        lensEnabled = false,
        vibrancyEnabled = false,
        blurRadiusDp = 0f,
        surfaceAlpha = if (darkMode) 0.74f else 0.82f,
    )
}
