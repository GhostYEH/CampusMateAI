package com.example.campusai.ui.screens.counselor

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

fun interface CpmChatStreamer {
    suspend fun stream(question: String, onChunk: (String) -> Unit)
}

class CounselorViewModel(
    private val streamer: CpmChatStreamer,
    private val clock: () -> Long = System::currentTimeMillis,
) : ViewModel() {
    private val _uiState = MutableStateFlow(CpmCounselorUiState())
    val uiState: StateFlow<CpmCounselorUiState> = _uiState.asStateFlow()

    fun updateInput(value: String) = _uiState.update { it.copy(input = value) }

    fun send(prompt: String = _uiState.value.input) {
        val question = prompt.trim()
        if (question.isEmpty() || _uiState.value.sending) return
        val submitted = CpmCounselorStateReducer.submit(_uiState.value, question, clock())
        val assistantId = submitted.messages.last().id
        _uiState.value = submitted
        viewModelScope.launch {
            try {
                var received = false
                streamer.stream(question) { chunk ->
                    if (chunk.isNotEmpty()) {
                        received = true
                        _uiState.update { CpmCounselorStateReducer.appendChunk(it, assistantId, chunk) }
                    }
                }
                if (!received) throw IllegalStateException("empty AI stream")
                _uiState.update { CpmCounselorStateReducer.complete(it, assistantId) }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                _uiState.update {
                    CpmCounselorStateReducer.fail(
                        it,
                        assistantId,
                        error.message ?: "AI 服务暂时不可用",
                    )
                }
            }
        }
    }

    fun retryLast() {
        val prompt = _uiState.value.messages.lastOrNull { it.role == "user" }?.content.orEmpty()
        send(prompt)
    }

    fun shuffleRecommendations() = _uiState.update { state ->
        state.copy(recommendationOffset = (state.recommendationOffset + 4).mod(CpmPromptCatalog.all.size))
    }

    fun sendPlaybackCommand(command: DigitalHumanCommand) = _uiState.update { state ->
        state.copy(playbackCommand = command, playbackCommandId = state.playbackCommandId + 1)
    }
}

class CounselorViewModelFactory(private val repository: AppRepository) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = CounselorViewModel(
        streamer = CpmChatStreamer { question, onChunk ->
            repository.streamChat(message = question, onChunk = { chunk -> onChunk(chunk) })
        },
    ) as T
}
