package com.example.campusai.data.repository

import android.app.Application
import com.example.campusai.data.remote.ChaoxingSyncStatusResponse
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import retrofit2.Response

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33], application = Application::class)
class ChaoxingResponsePolicyTest {
    private val damaged = """{"code":"CHAOXING_CREDENTIALS_UNAVAILABLE","message":"连接信息无法读取"}"""

    @Test
    fun damagedCredentialsEnterExistingReconnectStateAndStopWorkerRetries() {
        val response = Response.error<ChaoxingSyncStatusResponse>(503, damaged.toResponseBody())
        assertEquals("expired", chaoxingStatus(response)?.status)
        // ViewModel and Worker already handle this result as a reauth failure.
        assertEquals("reauth_required", chaoxingSyncFailure(503, damaged))
    }

    @Test
    fun temporaryFailuresKeepConnectionIndeterminateAndRemainRetryable() {
        for (body in listOf("unavailable", "{}", """{"code":"UNAVAILABLE","message":"CHAOXING_CREDENTIALS_UNAVAILABLE"}""")) {
            assertNull(chaoxingStatus(Response.error(503, body.toResponseBody())))
            assertEquals("同步失败: 503", chaoxingSyncFailure(503, body))
        }
    }

    @Test
    fun successfulStatusAndExistingAuthFailuresKeepTheirBehavior() {
        val online = ChaoxingSyncStatusResponse(status = "online", last_synced_at = "2026-10-04T00:00:00Z")
        assertSame(online, chaoxingStatus(Response.success(online)))
        assertEquals("reauth_required", chaoxingSyncFailure(401, "reauth_required"))
        assertEquals("verification_required", chaoxingSyncFailure(403, "verification_required"))
    }
}
