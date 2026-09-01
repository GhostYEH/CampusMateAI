package com.example.campusai.data.repository

import com.example.campusai.data.remote.ApiService
import java.lang.reflect.Proxy
import kotlinx.coroutines.runBlocking
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertTrue
import org.junit.Test
import retrofit2.Response

class EduRepositoryTest {
    @Test
    fun unbindFailsWhenServerRejectsRequest() = runBlocking {
        val api = Proxy.newProxyInstance(
            ApiService::class.java.classLoader,
            arrayOf(ApiService::class.java),
        ) { _, method, _ ->
            when (method.name) {
                "eduUnbind" -> Response.error<Unit>(503, "unavailable".toResponseBody())
                else -> error("Unexpected API call: ${method.name}")
            }
        } as ApiService

        val result = EduRepository(api).unbind()

        assertTrue(result.isFailure)
    }
}
