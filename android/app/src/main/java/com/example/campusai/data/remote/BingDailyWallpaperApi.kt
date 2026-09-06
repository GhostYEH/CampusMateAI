package com.example.campusai.data.remote

import com.example.campusai.data.wallpaper.BingDailyWallpaperResponse
import retrofit2.http.GET
import retrofit2.http.Query

interface BingDailyWallpaperApi {
    @GET("api/v1/image/bing-daily")
    suspend fun fetch(
        @Query("resolution") resolution: String = "1080",
        @Query("format") format: String = "json",
    ): BingDailyWallpaperResponse
}
