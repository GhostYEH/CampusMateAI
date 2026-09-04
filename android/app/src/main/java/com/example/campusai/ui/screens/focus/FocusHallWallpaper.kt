package com.example.campusai.ui.screens.focus

import androidx.annotation.DrawableRes
import com.example.campusai.R
import kotlin.random.Random

internal val focusHallWallpaperResources = listOf(
    R.drawable.focus_hall_wallpaper_misty_forest,
    R.drawable.focus_hall_wallpaper_alpine_lake,
    R.drawable.focus_hall_wallpaper_bamboo_stream,
    R.drawable.focus_hall_wallpaper_coastal_twilight,
    R.drawable.focus_hall_wallpaper_rainwashed_meadow,
)

@DrawableRes
internal fun chooseFocusHallWallpaper(
    @DrawableRes previousResource: Int?,
    randomIndex: Int,
): Int {
    val candidates = if (previousResource == null) {
        focusHallWallpaperResources
    } else {
        focusHallWallpaperResources.filterNot { it == previousResource }
    }
    return candidates[Math.floorMod(randomIndex, candidates.size)]
}

internal object FocusHallWallpaperPicker {
    @DrawableRes
    private var previousResource: Int? = null

    @Synchronized
    @DrawableRes
    fun next(): Int = chooseFocusHallWallpaper(
        previousResource = previousResource,
        randomIndex = Random.nextInt(),
    ).also { previousResource = it }
}
