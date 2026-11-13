package com.example.campusai.ui.components

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.example.campusai.data.audio.WavSpeechRecorder
import com.example.campusai.data.remote.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import retrofit2.HttpException
import java.io.File

/**
 * 麦克风按钮：点一下开始录音，再点一下结束并上传到后端本地 SenseVoice 识别，
 * 把文本通过 [onText] 回填。识别为空（没听清）或失败时通过 [onMessage] 提示。
 *
 * 自包含权限申请与录音器生命周期；离开界面时自动取消录音。供 cpm 与课堂/自习室
 * 的文字输入框复用，避免各处重复实现。
 */
@Composable
fun SpeechInputButton(
    onText: (String) -> Unit,
    onMessage: (String) -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    tint: Color = Color(0xFF3D5AFE),
    recordingTint: Color = Color(0xFFE53935),
) {
    val context = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val currentOnText by rememberUpdatedState(onText)
    val currentOnMessage by rememberUpdatedState(onMessage)
    val currentEnabled by rememberUpdatedState(enabled)
    var recording by remember { mutableStateOf(false) }
    var transcribing by remember { mutableStateOf(false) }
    var requestJob by remember { mutableStateOf<Job?>(null) }
    var finishSignal by remember { mutableStateOf<CompletableDeferred<Unit>?>(null) }
    var generation by remember { mutableStateOf(0) }

    fun cancelCurrent() {
        generation++
        requestJob?.cancel()
        requestJob = null
        finishSignal = null
        recording = false
        transcribing = false
    }

    DisposableEffect(owner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) cancelCurrent()
        }
        owner.lifecycle.addObserver(observer)
        onDispose {
            owner.lifecycle.removeObserver(observer)
            cancelCurrent()
        }
    }

    val start = {
        if (!recording && !transcribing && currentEnabled &&
            owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
            val recorder = WavSpeechRecorder(context)
            val completed = CompletableDeferred<Unit>()
            val run = ++generation
            finishSignal = completed
            recording = true
            requestJob = scope.launch {
                var audioFile: File? = null
                try {
                    val started = withContext(Dispatchers.IO) {
                        recorder.start { completed.complete(Unit) }
                    }
                    if (!started) {
                        currentOnMessage("无法启动麦克风，请检查权限后重试")
                        return@launch
                    }
                    // Manual stop and the recorder's hard limit share one completion path.
                    completed.await()
                    recording = false
                    transcribing = true
                    val file = withContext(Dispatchers.IO) {
                        recorder.stop().also { audioFile = it }
                    }
                    if (file == null) {
                        currentOnMessage("没有录到声音，请再说一次")
                        return@launch
                    }
                    val response = ApiClient.speechApi.transcribeSpeech(
                        MultipartBody.Part.createFormData(
                            "audio", "speech.wav", file.asRequestBody("audio/wav".toMediaType()),
                        ),
                    )
                    if (!response.isSuccessful) throw HttpException(response)
                    val text = response.body()?.text.orEmpty().trim()
                    if (generation == run && owner.lifecycle.currentState.isAtLeast(Lifecycle.State.STARTED)) {
                        if (text.isBlank()) currentOnMessage("没听清，请再说一次") else currentOnText(text)
                    }
                } catch (error: CancellationException) {
                    throw error
                } catch (error: Exception) {
                    if (generation == run) {
                        currentOnMessage(when ((error as? HttpException)?.code()) {
                            401 -> "登录已失效，请重新登录后使用语音输入"
                            413 -> "录音超过服务端限制，请缩短后重试"
                            503 -> "语音识别繁忙或暂不可用，请稍后重试"
                            else -> "语音识别暂时不可用，请稍后重试"
                        })
                    }
                } finally {
                    // Cancellation must also release the mic and delete audio, off the UI thread.
                    withContext(NonCancellable + Dispatchers.IO) {
                        recorder.cancel()
                        audioFile?.delete()
                    }
                    if (generation == run) {
                        recording = false
                        transcribing = false
                        requestJob = null
                        finishSignal = null
                    }
                }
            }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) start() else currentOnMessage("需要麦克风权限才能语音输入")
    }

    val hasPermission = ContextCompat.checkSelfPermission(
        context, Manifest.permission.RECORD_AUDIO,
    ) == PackageManager.PERMISSION_GRANTED

    IconButton(
        onClick = {
            when {
                transcribing -> Unit
                recording -> finishSignal?.complete(Unit)
                !hasPermission -> permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                else -> start()
            }
        },
        enabled = (enabled || recording) && !transcribing,
        modifier = modifier.size(40.dp).clip(CircleShape),
    ) {
        when {
            transcribing -> CircularProgressIndicator(
                modifier = Modifier.size(20.dp), strokeWidth = 2.dp, color = tint,
            )
            recording -> Icon(Icons.Default.Stop, contentDescription = "结束录音", tint = recordingTint)
            else -> Icon(Icons.Default.Mic, contentDescription = "语音输入", tint = tint)
        }
    }
}
