package com.example.campusai.data.remote

import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.example.campusai.BuildConfig
import java.util.concurrent.TimeUnit

object ApiClient {
    private val BASE_URL = BuildConfig.API_BASE_URL

    private var accessToken: String? = null

    fun setToken(token: String?) {
        accessToken = token
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG) {
            HttpLoggingInterceptor.Level.BODY
        } else {
            HttpLoggingInterceptor.Level.NONE
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .addInterceptor { chain ->
            val request = chain.request()
            val builder = request.newBuilder()
            accessToken?.let { builder.header("Authorization", "Bearer $it") }
            chain.proceed(builder.build())
        }
        .addInterceptor(loggingInterceptor)
        .build()

    private val moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()

    val api: ApiService = retrofit.create(ApiService::class.java)

    suspend fun probeBackend(): Boolean {
        return try {
            val response = api.health()
            response.isSuccessful
        } catch (_: Exception) {
            false
        }
    }
}
