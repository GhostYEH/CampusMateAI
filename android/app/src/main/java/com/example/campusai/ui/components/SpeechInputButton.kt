package com.example.campusai.ui.components

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
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
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import com.example.campusai.data.audio.WavSpeechRecorder
import com.example.campusai.data.remote.ApiClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody

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
    val scope = rememberCoroutineScope()
    val recorder = remember(context) { WavSpeechRecorder(context) }
    var recording by remember { mutableStateOf(false) }
    var transcribing by remember { mutableStateOf(false) }

    DisposableEffect(recorder) {
        onDispose { recorder.cancel() }
    }

    val start = {
        if (!recording && !transcribing) {
            if (recorder.start()) {
                recording = true
            } else {
                onMessage("无法启动麦克风，请检查权限后重试")
            }
        }
    }

    val finish = {
        if (recording) {
            recording = false
            val file = recorder.stop()
            if (file == null) {
                onMessage("没有录到声音，请再说一次")
            } else {
                transcribing = true
                scope.launch {
                    val result = withContext(Dispatchers.IO) {
                        runCatching {
                            val audioPart = MultipartBody.Part.createFormData(
                                "audio", "speech.wav",
                                file.asRequestBody("audio/wav".toMediaType()),
                            )
                            val response = ApiClient.api.transcribeSpeech(audioPart)
                            if (!response.isSuccessful) {
                                throw IllegalStateException("语音识别失败(${response.code()})")
                            }
                            response.body()?.text.orEmpty().trim()
                        }
                    }
                    file.delete()
                    transcribing = false
                    result.onSuccess { text ->
                        if (text.isBlank()) onMessage("没听清，请再说一次") else onText(text)
                    }.onFailure {
                        onMessage("语音识别暂时不可用，请稍后重试")
                    }
                }
            }
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) start() else onMessage("需要麦克风权限才能语音输入")
    }

    val hasPermission = ContextCompat.checkSelfPermission(
        context, Manifest.permission.RECORD_AUDIO,
    ) == PackageManager.PERMISSION_GRANTED

    IconButton(
        onClick = {
            when {
                transcribing -> Unit
                recording -> finish()
                !hasPermission -> permissionLauncher.launch(Manifest.permission.RECORD_AUDIO)
                else -> start()
            }
        },
        enabled = enabled && !transcribing,
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
