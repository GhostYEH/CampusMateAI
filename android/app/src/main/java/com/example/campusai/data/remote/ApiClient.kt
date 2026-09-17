package com.example.campusai.data.remote

import okhttp3.OkHttpClient
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.moshi.MoshiConverterFactory
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import com.example.campusai.data.remote.agent.CounselorFinalMetaDto
import com.example.campusai.data.remote.agent.CounselorSseParser
import com.example.campusai.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.util.concurrent.TimeUnit

object ApiClient {
    private val BASE_URL = BuildConfig.API_BASE_URL

    private var accessToken: String? = null

    fun setToken(token: String?) {
        accessToken = token
    }

    /**
     * 由 AppRepository 注入的 token 刷新回调：同步返回新的 access token，失败返回 null。
     * OkHttp Authenticator 在收到 401 时调用它自动续期，避免用户看到「登录已失效」。
     */
    private var tokenRefresher: (() -> String?)? = null

    fun setTokenRefresher(refresher: (() -> String?)?) {
        tokenRefresher = refresher
    }

    @Volatile
    private var lastRefreshedToken: String? = null

    private fun responseCount(response: okhttp3.Response): Int {
        var count = 1
        var prior = response.priorResponse
        while (prior != null) { count++; prior = prior.priorResponse }
        return count
    }

    private val authenticator = okhttp3.Authenticator { _, response ->
        if (responseCount(response) >= 2) return@Authenticator null
        val refresher = tokenRefresher ?: return@Authenticator null
        val requestToken = response.request.header("Authorization")?.removePrefix("Bearer ")
        synchronized(ApiClient) {
            val current = accessToken
            if (current != null && current != requestToken && current == lastRefreshedToken) {
                return@Authenticator response.request.newBuilder()
                    .header("Authorization", "Bearer $current")
                    .build()
            }
            val newToken = refresher()
            if (newToken == null) return@Authenticator null
            lastRefreshedToken = newToken
            response.request.newBuilder()
                .header("Authorization", "Bearer $newToken")
                .build()
        }
    }

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG) {
            // Request/response bodies can contain chat text, passwords and tokens.
            HttpLoggingInterceptor.Level.BASIC
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
        .authenticator(authenticator)
        .build()

    private val chaoxingHttpClient = okHttpClient.newBuilder()
        .readTimeout(45, TimeUnit.SECONDS)
        .callTimeout(60, TimeUnit.SECONDS)
        .build()

    private val counselorStreamClient = okHttpClient.newBuilder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    val agentSseStreamClient: OkHttpClient = okHttpClient.newBuilder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    val agentSse: com.example.campusai.data.remote.agent.AgentSseClient =
        com.example.campusai.data.remote.agent.AgentSseClient(
            baseUrl = BASE_URL,
            tokenProvider = ::currentAccessToken,
            tokenRefresher = tokenRefresh@{
                val current = accessToken
                if (current.isNullOrBlank()) return@tokenRefresh null
                try {
                    val response = kotlinx.coroutines.runBlocking {
                        authApi.refresh(RefreshRequest(current))
                    }
                    val newToken: String? = response.body()?.access_token
                    if (response.isSuccessful && newToken != null) {
                        setToken(newToken)
                        newToken
                    } else null
                } catch (_: Exception) { null }
            },
            client = agentSseStreamClient,
        )

    private val moshi = Moshi.Builder()
        .addLast(KotlinJsonAdapterFactory())
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()

    val api: ApiService = retrofit.create(ApiService::class.java)

    /** Same authenticated backend, but converted to WebSocket only inside the voice transport. */
    fun websocketUrl(path: String): String {
        val root = BASE_URL.removeSuffix("/")
        val scheme = if (root.startsWith("https://")) "wss://" else "ws://"
        return root.replaceFirst(Regex("^https?://"), scheme) + "/" + path.removePrefix("/")
    }

    fun currentAccessToken(): String? = accessToken

    // 不附加 Authorization、不挂 Authenticator 的客户端，专供 auth/refresh 接口使用，
    // 避免 refresh 请求自身 401 时触发 Authenticator 形成递归。
    private val noAuthClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(8, TimeUnit.SECONDS)
        .addInterceptor(loggingInterceptor)
        .build()

    private val hitokotoRetrofit = Retrofit.Builder()
        .baseUrl("https://v1.hitokoto.cn/")
        .client(noAuthClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()

    val hitokotoApi: HitokotoApi = hitokotoRetrofit.create(HitokotoApi::class.java)

    private val bingDailyWallpaperRetrofit = Retrofit.Builder()
        .baseUrl("https://uapis.cn/")
        .client(noAuthClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()

    val bingDailyWallpaperApi: BingDailyWallpaperApi =
        bingDailyWallpaperRetrofit.create(BingDailyWallpaperApi::class.java)

    val authApi: ApiService = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(noAuthClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()
        .create(ApiService::class.java)

    private val chaoxingRetrofit = Retrofit.Builder()
        .baseUrl(BASE_URL)
        .client(chaoxingHttpClient)
        .addConverterFactory(MoshiConverterFactory.create(moshi).asLenient())
        .build()
    val chaoxingApi: ApiService = chaoxingRetrofit.create(ApiService::class.java)

    private val staticOrigin: String = run {
        val idx = BASE_URL.indexOf("://")
        val afterScheme = if (idx >= 0) BASE_URL.substring(idx + 3) else BASE_URL
        val scheme = if (idx >= 0) BASE_URL.substring(0, idx) else "http"
        val slash = afterScheme.indexOf('/')
        val host = if (slash >= 0) afterScheme.substring(0, slash) else afterScheme
        "$scheme://$host"
    }

    fun resolveStaticUrl(url: String?): String? {
        if (url.isNullOrBlank()) return null
        if (url.startsWith("http://") || url.startsWith("https://")) return url
        return if (url.startsWith("/")) "$staticOrigin$url" else "$staticOrigin/$url"
    }

    suspend fun streamCounselor(
        request: ChatRequest,
        onChunk: suspend (String) -> Unit,
        onMeta: suspend (CounselorFinalMetaDto) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        val payload = moshi.adapter(ChatRequest::class.java).toJson(request.copy(stream = true))
        val httpRequest = Request.Builder()
            .url("${BASE_URL}counselor/chat")
            .header("Accept", "text/event-stream")
            .apply { accessToken?.let { header("Authorization", "Bearer $it") } }
            .post(payload.toRequestBody("application/json; charset=utf-8".toMediaType()))
            .build()
        counselorStreamClient.newCall(httpRequest).execute().use { response ->
            if (!response.isSuccessful) throw java.io.IOException("AI 服务请求失败 (${response.code})")
            val source = response.body?.source() ?: throw java.io.IOException("AI 服务没有返回内容")
            var event = ""
            val data = StringBuilder()
            // 同一个流里只认第一个 done：代理重放/重复事件不得二次触发副作用。
            var doneSeen = false

            /** 派发一条已完整收到的事件（空行分隔，或流结束时 flush）。 */
            suspend fun dispatch() {
                if (event.isEmpty() || data.isEmpty()) {
                    event = ""
                    data.clear()
                    return
                }
                val current = event
                val payload = data.toString()
                event = ""
                data.clear()
                when (current) {
                    "chunk" -> {
                        val text = org.json.JSONObject(payload).optString("text")
                        if (text.isNotEmpty()) {
                            withContext(Dispatchers.Main.immediate) { onChunk(text) }
                        }
                    }
                    "done" -> {
                        if (!doneSeen) {
                            doneSeen = true
                            CounselorSseParser.parseFinalMeta(payload)?.let { meta ->
                                withContext(Dispatchers.Main.immediate) { onMeta(meta) }
                            }
                        }
                    }
                    "error" -> throw java.io.IOException(
                        org.json.JSONObject(payload).optString("message", "AI 服务生成失败"),
                    )
                }
            }

            while (!source.exhausted()) {
                val line = source.readUtf8Line() ?: break
                when {
                    line.startsWith("event:") -> event = line.removePrefix("event:").trim()
                    line.startsWith("data:") -> {
                        // SSE permits one optional space after the colon. Preserve all
                        // remaining whitespace because a streamed text chunk may begin
                        // or end with meaningful spacing.
                        if (data.isNotEmpty()) data.append('\n')
                        data.append(line.removePrefix("data:").removePrefix(" "))
                    }
                    line.isEmpty() -> dispatch()
                }
            }
            // 连接在最后一条事件之后直接关闭（没有结尾空行）时，最后一条事件
            // **必须照样 flush** —— 否则最终的 done 元数据（含互动课堂提案）会丢失。
            dispatch()
        }
    }

    suspend fun probeBackend(): Boolean {
        return try {
            val response = api.health()
            response.isSuccessful
        } catch (_: Exception) {
            false
        }
    }
}
