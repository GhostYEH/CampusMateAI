package com.example.campusai.data.focus.scene

import android.content.Context
import androidx.annotation.RawRes
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.Player
import androidx.media3.exoplayer.ExoPlayer
import com.example.campusai.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

object FocusSceneAudioResources {
    @RawRes
    fun resourceId(scene: FocusScene): Int = when (scene) {
        FocusScene.RAINY_ROOM -> R.raw.focus_ambient_rainy_room
        FocusScene.QUIET_LIBRARY -> R.raw.focus_ambient_quiet_library
        FocusScene.FOREST_MORNING -> R.raw.focus_ambient_forest_morning
    }
}

class FocusAmbientAudioController(context: Context) {
    private val appContext = context.applicationContext
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val player = ExoPlayer.Builder(appContext).build().apply {
        setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(C.USAGE_MEDIA)
                .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC)
                .build(),
            true,
        )
        repeatMode = Player.REPEAT_MODE_ONE
        volume = 0f
    }

    private var currentScene: FocusScene? = null
    private var targetVolume = 0f
    private var volumeJob: Job? = null
    private var released = false

    fun setScene(scene: FocusScene) {
        if (released || currentScene == scene) return
        currentScene = scene
        player.setMediaItem(
            MediaItem.fromUri(
                "android.resource://${appContext.packageName}/${FocusSceneAudioResources.resourceId(scene)}",
            ),
        )
        player.prepare()
        if (targetVolume > 0f) player.play()
    }

    fun setTargetVolume(volume: Float) {
        if (released) return
        targetVolume = volume.takeIf(Float::isFinite)?.coerceIn(0f, 1f) ?: 0f
        volumeJob?.cancel()
        volumeJob = scope.launch {
            val startVolume = player.volume
            if (targetVolume > 0f) player.play()
            val steps = 11
            repeat(steps) { index ->
                val progress = (index + 1f) / steps
                player.volume = startVolume + (targetVolume - startVolume) * progress
                delay((FADE_DURATION_MS / steps.toFloat()).roundToInt().toLong())
            }
            player.volume = targetVolume
            if (targetVolume == 0f) player.pause()
        }
    }

    fun release() {
        if (released) return
        released = true
        volumeJob?.cancel()
        scope.cancel()
        player.release()
    }

    private companion object {
        const val FADE_DURATION_MS = 220
    }
}
