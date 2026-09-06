package com.example.campusai.data.wallpaper

data class BingDailyWallpaperResponse(
    val date: String? = null,
    val title: String? = null,
    val image_url: String? = null,
    val image_url_4k: String? = null,
    val image_url_1080: String? = null,
)

data class BingDailyWallpaper(
    val imageUrl: String,
    val title: String,
    val date: String,
)

data class BingDailyWallpaperState(
    val wallpaper: BingDailyWallpaper? = null,
    val isLoading: Boolean = false,
    val unavailable: Boolean = false,
)

fun BingDailyWallpaperResponse.preferredImageUrl(): String? = listOf(
    image_url_1080,
    image_url,
    image_url_4k,
).firstOrNull { url ->
    url?.trim()?.let { it.startsWith("https://") || it.startsWith("http://") } == true
}
