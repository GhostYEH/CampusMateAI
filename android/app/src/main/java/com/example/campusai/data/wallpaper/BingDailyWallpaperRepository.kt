package com.example.campusai.data.wallpaper

import com.example.campusai.data.remote.ApiClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class BingDailyWallpaperRepository(
    private val fetcher: suspend () -> BingDailyWallpaperResponse = {
        ApiClient.bingDailyWallpaperApi.fetch()
    },
) {
    private val _state = MutableStateFlow(BingDailyWallpaperState())
    val state: StateFlow<BingDailyWallpaperState> = _state.asStateFlow()

    suspend fun refresh() {
        if (_state.value.isLoading || _state.value.wallpaper != null) return
        _state.value = BingDailyWallpaperState(isLoading = true)
        try {
            val response = fetcher()
            val imageUrl = response.preferredImageUrl()
                ?.trim()
                ?: throw IllegalStateException("必应壁纸响应缺少图片地址")
            _state.value = BingDailyWallpaperState(
                wallpaper = BingDailyWallpaper(
                    imageUrl = imageUrl,
                    title = response.title.orEmpty().trim(),
                    date = response.date.orEmpty().trim(),
                ),
            )
        } catch (_: Exception) {
            _state.value = BingDailyWallpaperState(unavailable = true)
        }
    }
}
