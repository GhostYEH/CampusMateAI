package com.example.campusai.ui.glass

enum class CampusGlassQuality {
    FULL,
    BLUR,
    PAINTED,
}

enum class CampusGlassRole {
    NAVIGATION,
    PANEL,
    CONTROL,
    DENSE,
}

data class CampusGlassEffects(
    val blurRadiusDp: Float,
    val lensAtRest: Boolean,
    val lensOnPress: Boolean,
    val glowAtRest: Boolean,
)

data class CampusGlassProfile(
    val quality: CampusGlassQuality,
    val blurEnabled: Boolean,
    val lensEnabled: Boolean,
    val glowAnimationEnabled: Boolean,
) {
    fun effectsFor(role: CampusGlassRole): CampusGlassEffects = when (role) {
        CampusGlassRole.NAVIGATION -> CampusGlassEffects(
            blurRadiusDp = 8f,
            lensAtRest = lensEnabled,
            lensOnPress = lensEnabled,
            glowAtRest = true,
        )
        CampusGlassRole.PANEL -> CampusGlassEffects(
            blurRadiusDp = 7f,
            lensAtRest = false,
            lensOnPress = false,
            glowAtRest = false,
        )
        CampusGlassRole.CONTROL -> CampusGlassEffects(
            blurRadiusDp = 3f,
            lensAtRest = false,
            lensOnPress = lensEnabled,
            glowAtRest = false,
        )
        CampusGlassRole.DENSE -> CampusGlassEffects(
            blurRadiusDp = 0f,
            lensAtRest = false,
            lensOnPress = false,
            glowAtRest = false,
        )
    }
}

fun campusGlassProfile(
    apiLevel: Int,
    reduceMotion: Boolean,
): CampusGlassProfile {
    val quality = when {
        apiLevel >= 33 -> CampusGlassQuality.FULL
        apiLevel >= 31 -> CampusGlassQuality.BLUR
        else -> CampusGlassQuality.PAINTED
    }
    return CampusGlassProfile(
        quality = quality,
        blurEnabled = quality != CampusGlassQuality.PAINTED,
        lensEnabled = quality == CampusGlassQuality.FULL,
        glowAnimationEnabled = !reduceMotion,
    )
}
