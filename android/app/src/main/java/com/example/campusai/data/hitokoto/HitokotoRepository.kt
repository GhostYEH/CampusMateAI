package com.example.campusai.data.hitokoto

import com.example.campusai.data.remote.ApiClient
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class HitokotoResponse(
    val hitokoto: String = "",
    val from: String? = null,
    val uuid: String? = null,
)

data class HitokotoQuote(
    val text: String,
    val source: String,
    val uuid: String,
)

data class HitokotoState(
    val quote: HitokotoQuote? = null,
    val isLoading: Boolean = false,
    val unavailable: Boolean = false,
) {
    fun displayText(): String = quote?.text?.takeIf { it.isNotBlank() }
        ?: if (isLoading) "一言加载中…" else "暂时无法获取一言"
}

class HitokotoRepository(
    private val fetcher: suspend () -> HitokotoResponse = { ApiClient.hitokotoApi.fetch() },
) {
    private val _state = MutableStateFlow(HitokotoState())
    val state: StateFlow<HitokotoState> = _state.asStateFlow()

    suspend fun refresh() {
        if (_state.value.isLoading || _state.value.quote != null) return
        _state.value = HitokotoState(isLoading = true)
        try {
            val response = fetcher()
            val text = response.hitokoto.trim()
            if (text.isBlank()) throw IllegalStateException("一言响应缺少正文")
            _state.value = HitokotoState(
                quote = HitokotoQuote(
                    text = text,
                    source = response.from.orEmpty().trim(),
                    uuid = response.uuid.orEmpty().trim(),
                ),
            )
        } catch (_: Exception) {
            _state.value = HitokotoState(unavailable = true)
        }
    }
}
