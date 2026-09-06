package com.example.campusai.data.remote

import com.example.campusai.data.hitokoto.HitokotoResponse
import retrofit2.http.GET

interface HitokotoApi {
    @GET("?encode=json")
    suspend fun fetch(): HitokotoResponse
}
