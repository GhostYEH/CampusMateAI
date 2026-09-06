package com.example.campusai.ui.screens.shell

internal data class LiquidGlassDockProfile(
    val blurEnabled: Boolean,
    val lensEnabled: Boolean,
    val vibrancyEnabled: Boolean,
    val blurRadiusDp: Float,
    val surfaceAlpha: Float,
    val chromaticEdgeAlpha: Float,
    val shadowColorArgb: Long,
)

internal data class LiquidGlassDockInteractionProfile(
    val clickGlowEnabled: Boolean,
    val clickGlowDurationMillis: Int,
    val clickGlowRadiusDp: Float,
)

internal fun liquidGlassDockInteractionProfile(
    reduceMotion: Boolean,
): LiquidGlassDockInteractionProfile = LiquidGlassDockInteractionProfile(
    clickGlowEnabled = !reduceMotion,
    clickGlowDurationMillis = if (reduceMotion) 0 else 300,
    clickGlowRadiusDp = 30f,
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
        chromaticEdgeAlpha = 0.16f,
        shadowColorArgb = if (darkMode) 0x80000000L else 0x260B1830L,
    )
    apiLevel >= 31 -> LiquidGlassDockProfile(
        blurEnabled = true,
        lensEnabled = false,
        vibrancyEnabled = false,
        blurRadiusDp = 12f,
        surfaceAlpha = if (darkMode) 0.46f else 0.52f,
        chromaticEdgeAlpha = 0.09f,
        shadowColorArgb = if (darkMode) 0x80000000L else 0x260B1830L,
    )
    else -> LiquidGlassDockProfile(
        blurEnabled = false,
        lensEnabled = false,
        vibrancyEnabled = false,
        blurRadiusDp = 0f,
        surfaceAlpha = if (darkMode) 0.74f else 0.82f,
        chromaticEdgeAlpha = if (darkMode) 0.08f else 0.05f,
        shadowColorArgb = if (darkMode) 0x80000000L else 0x260B1830L,
    )
}
