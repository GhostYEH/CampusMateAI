package com.example.campusai.data.remote

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.async
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class AuthTokenRefreshCoordinatorTest {
    private class FakeAuth {
        var token: String? = "access-0"
        var refreshToken: String? = "refresh-0"
        var epoch = 0
        var requests = 0
        var hold: CompletableDeferred<Unit>? = null
        var failure: Exception? = null

        fun coordinator() = AuthTokenRefreshCoordinator(
            tokenProvider = { token },
            refreshTokenProvider = { refreshToken },
            refreshRequest = { used ->
                requests += 1
                hold?.await()
                if (failure != null) {
                    failure = null
                    null
                } else if (used != refreshToken) {
                    null
                } else {
                    AuthTokenPair("access-$requests", "refresh-$requests")
                }
            },
            onToken = { pair ->
                token = pair.accessToken
                refreshToken = pair.refreshToken
            },
            sessionEpoch = { epoch },
            isExpired = { false },
        )
    }

    @Test
    fun `concurrent renewals make a single request and share the new token`() = runTest {
        val auth = FakeAuth()
        val coordinator = auth.coordinator()
        val gate = CompletableDeferred<Unit>()
        auth.hold = gate
        val first = async { coordinator.refresh() }
        val second = async { coordinator.refresh() }
        runCurrent()
        gate.complete(Unit)
        assertEquals("access-1", first.await())
        assertEquals("access-1", second.await())
        assertEquals("同会话只发一次续签", 1, auth.requests)
        assertEquals("access-1", auth.token)
    }

    @Test
    fun `logout during renewal drops the late result`() = runTest {
        val auth = FakeAuth()
        val coordinator = auth.coordinator()
        val gate = CompletableDeferred<Unit>()
        auth.hold = gate
        val renewal = async { coordinator.refresh() }
        runCurrent()
        // 请求在途时退出登录并切到新会话。
        auth.epoch += 1
        auth.token = null
        gate.complete(Unit)
        assertNull("退出后的旧结果不得复活 token", renewal.await())
        assertNull(auth.token)
    }

    @Test
    fun `account switch during renewal does not apply the old token`() = runTest {
        val auth = FakeAuth()
        val coordinator = auth.coordinator()
        val gate = CompletableDeferred<Unit>()
        auth.hold = gate
        val renewal = async { coordinator.refresh() }
        runCurrent()
        auth.epoch += 1
        auth.token = "access-new-session"
        gate.complete(Unit)
        assertNull(renewal.await())
        assertEquals("access-new-session", auth.token)
    }

    @Test
    fun `waiting caller reuses token refreshed by the first caller`() = runTest {
        val auth = FakeAuth()
        val coordinator = auth.coordinator()
        val gate = CompletableDeferred<Unit>()
        auth.hold = gate
        val first = async { coordinator.refresh() }
        val second = async { coordinator.refresh() }
        runCurrent()
        gate.complete(Unit)
        first.await()
        // 第二个调用在锁内看到 token 已变化，直接复用而不再次续签。
        assertEquals("access-1", second.await())
        assertEquals(1, auth.requests)
    }

    @Test
    fun `failed renewal returns null without applying a token`() = runTest {
        val auth = FakeAuth()
        val coordinator = auth.coordinator()
        auth.failure = IOException("timeout")
        assertNull(coordinator.refresh())
        assertEquals("access-0", auth.token)
    }
}
