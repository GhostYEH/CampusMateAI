package com.example.campusai.data.remote

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

data class AuthTokenPair(val accessToken: String, val refreshToken: String)

/**
 * 登录会话内的 token 续签协调器。
 *
 * - 并发续签只发一次请求，等待者复用刚刷新好的 token；
 * - 请求返回后校验会话代次，退出或换号后的旧结果直接丢弃；
 * - 不依赖 Android API，JVM 测试可复现并发、退出和换号时序。
 */
class AuthTokenRefreshCoordinator(
    private val tokenProvider: () -> String?,
    private val refreshTokenProvider: suspend () -> String?,
    private val refreshRequest: suspend (String) -> AuthTokenPair?,
    private val onToken: suspend (AuthTokenPair) -> Unit,
    private val sessionEpoch: () -> Int,
    private val isExpired: (String) -> Boolean,
) {
    private val mutex = Mutex()

    suspend fun refresh(): String? {
        val tokenBeforeWaiting = tokenProvider()
        return mutex.withLock {
            val epoch = sessionEpoch()
            val refreshToken = refreshTokenProvider()?.takeIf { it.isNotBlank() }
                ?: return@withLock null
            val current = tokenProvider()
            if (current != null && current != tokenBeforeWaiting && !isExpired(current)) {
                return@withLock current
            }
            val pair = refreshRequest(refreshToken) ?: return@withLock null
            if (epoch != sessionEpoch()) return@withLock null
            onToken(pair)
            pair.accessToken
        }
    }
}
