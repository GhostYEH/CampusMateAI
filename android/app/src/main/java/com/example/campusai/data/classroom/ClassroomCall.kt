package com.example.campusai.data.classroom

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.view.TextureView
import com.example.campusai.data.remote.ClassroomRtcToken
import com.ss.bytertc.engine.RTCEngine
import com.ss.bytertc.engine.RTCRoom
import com.ss.bytertc.engine.RTCRoomConfig
import com.ss.bytertc.engine.UserInfo
import com.ss.bytertc.engine.VideoCanvas
import com.ss.bytertc.engine.VideoEncoderConfig
import com.ss.bytertc.engine.data.AudioRoute
import com.ss.bytertc.engine.data.EngineConfig
import com.ss.bytertc.engine.data.RemoteVideoConfig
import com.ss.bytertc.engine.data.StreamInfo
import com.ss.bytertc.engine.data.VideoSimulcastMode
import com.ss.bytertc.engine.handler.IRTCEngineEventHandler
import com.ss.bytertc.engine.handler.IRTCRoomEventHandler
import com.ss.bytertc.engine.type.AudioScenarioType
import com.ss.bytertc.engine.type.ChannelProfile
import com.ss.bytertc.engine.type.ConnectionState
import com.ss.bytertc.engine.type.NetworkQualityStats
import com.ss.bytertc.engine.type.RoomState
import com.ss.bytertc.engine.type.RoomStateChangeReason
import com.ss.bytertc.engine.type.SubscribeFallbackOptions
import com.ss.bytertc.engine.video.VideoCaptureConfig
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

data class ClassroomPeer(
    val uid: String, val streamId: String = "", val audio: Boolean = false, val video: Boolean = false,
)
data class ClassroomCallState(
    val phase: ClassroomCallPhase = ClassroomCallPhase.OFF,
    val microphone: Boolean = false, val camera: Boolean = false,
    val peers: Map<String, ClassroomPeer> = emptyMap(),
    val rttMs: Int? = null, val weakNetwork: Boolean = false, val error: String? = null,
)

/** Single owner; all SDK operations and callbacks are serialized on the main thread. */
class ClassroomCall(private val context: Context, private val renew: () -> Unit) {
    private val mutableState = MutableStateFlow(ClassroomCallState())
    val state = mutableState.asStateFlow()
    private val main = Handler(Looper.getMainLooper())
    private var engine: RTCEngine? = null
    private var room: RTCRoom? = null
    private var generation = 0
    val sessionGeneration: Int get() = generation
    private val connection = ClassroomConnectionTracker()
    private var frontCamera = true
    private val views = mutableMapOf<String, TextureView>()
    private val boundViews = mutableMapOf<String, Pair<TextureView, String>>()

    private fun dispatch(epoch: Int, action: () -> Unit) {
        main.post { if (epoch == generation && engine != null) action() }
    }

    fun prepareConnection() {
        check(Looper.myLooper() == Looper.getMainLooper())
        releaseResources()
        connection.begin()
        mutableState.value = ClassroomCallState(phase = connection.phase)
    }

    fun connect(token: ClassroomRtcToken) {
        prepareConnection()
        val epoch = generation
        try {
            engine = checkNotNull(RTCEngine.createRTCEngine(EngineConfig().apply {
                context = this@ClassroomCall.context.applicationContext
                appID = token.app_id
            }, object : IRTCEngineEventHandler() {
                override fun onError(code: Int) = dispatch(epoch) { fail("音视频引擎异常（$code），请重新连接") }
                override fun onConnectionStateChanged(state: Int, reason: Int) = dispatch(epoch) {
                    val transport = ConnectionState.fromId(state)
                    if (transport in listOf(ConnectionState.CONNECTION_STATE_RECONNECTING, ConnectionState.CONNECTION_STATE_LOST)) {
                        connection.transportChanged(false)
                        mutableState.update { it.copy(phase = connection.phase) }
                    }
                    if (transport in listOf(ConnectionState.CONNECTION_STATE_CONNECTED, ConnectionState.CONNECTION_STATE_RECONNECTED)) {
                        connection.transportChanged(true)
                    }
                    if (transport == ConnectionState.CONNECTION_STATE_FAILED) fail("网络连接失败，请重新连接课堂")
                }
                override fun onLocalAudioStateChanged(source: com.ss.bytertc.engine.IAudioSource, state: com.ss.bytertc.engine.data.LocalAudioStreamState, error: com.ss.bytertc.engine.data.LocalAudioStreamError) = dispatch(epoch) {
                    if (state == com.ss.bytertc.engine.data.LocalAudioStreamState.LOCAL_AUDIO_STREAM_STATE_FAILED && mutableState.value.microphone) {
                        microphone(false)
                        mutableState.update { it.copy(error = "麦克风采集失败，请检查权限或是否被其他应用占用") }
                    }
                }
                override fun onLocalVideoStateChanged(source: com.ss.bytertc.engine.IVideoSource, state: com.ss.bytertc.engine.type.LocalVideoStreamState, error: com.ss.bytertc.engine.type.LocalVideoStreamError) = dispatch(epoch) {
                    if (state == com.ss.bytertc.engine.type.LocalVideoStreamState.LOCAL_VIDEO_STREAM_STATE_FAILED && mutableState.value.camera) {
                        camera(false)
                        mutableState.update { it.copy(error = "摄像头采集失败，请检查权限或是否被其他功能占用") }
                    }
                }
            }))
            val rtc = checkNotNull(engine)
            checkCode(rtc.setAudioScenario(AudioScenarioType.CHATROOM))
            checkCode(rtc.setDefaultAudioRoute(AudioRoute.AUDIO_ROUTE_SPEAKERPHONE))
            checkCode(rtc.setVideoCaptureConfig(VideoCaptureConfig(640, 360, 15)))
            checkCode(rtc.setVideoEncoderConfig(VideoEncoderConfig().apply {
                width = 640; height = 360; frameRate = 15; maxBitrate = 500; minBitrate = 100
            }))
            checkCode(rtc.setLocalSimulcastMode(VideoSimulcastMode.VIDEO_SIMULCAST_MODE_ON_DEMAND))
            checkCode(rtc.setSubscribeFallbackOption(SubscribeFallbackOptions.SUBSCRIBE_FALLBACK_OPTIONS_AUDIO_ONLY))
            room = checkNotNull(rtc.createRTCRoom(token.room_id))
            val callRoom = checkNotNull(room)
            checkCode(callRoom.setRTCRoomEventHandler(object : IRTCRoomEventHandler() {
                override fun onRoomStateChangedWithReason(roomId: String, uid: String, state: RoomState, reason: RoomStateChangeReason) = dispatch(epoch) {
                    when (state) {
                        RoomState.JOIN_SUCCESS -> {
                            connection.roomJoined()
                            mutableState.update { it.copy(phase = connection.phase, error = null) }
                        }
                        RoomState.JOIN_FAILED, RoomState.LEFT -> fail(when (reason) {
                            RoomStateChangeReason.DUPLICATE_LOGIN -> "此账号已在其他设备加入通话，请选择一台设备使用"
                            RoomStateChangeReason.INVALID_TOKEN, RoomStateChangeReason.TOKEN_EXPIRED,
                            RoomStateChangeReason.UPDATE_TOKEN_WITH_INVALID_TOKEN -> "通话认证已失效，请重新连接课堂"
                            RoomStateChangeReason.ROOM_FORBIDDEN, RoomStateChangeReason.USER_FORBIDDEN,
                            RoomStateChangeReason.KICKED_OUT, RoomStateChangeReason.ROOM_DISMISS -> "课堂已关闭或已无法加入，请返回列表"
                            else -> "通话已断开，请检查网络后重新连接"
                        })
                        else -> Unit
                    }
                }
                override fun onUserJoined(info: UserInfo) = dispatch(epoch) {
                    mutableState.update { it.copy(peers = it.peers + (info.uid to (it.peers[info.uid] ?: ClassroomPeer(info.uid)))) }
                }
                override fun onUserLeave(uid: String, reason: Int) = dispatch(epoch) {
                    mutableState.value.peers[uid]?.streamId?.let { rtc.setRemoteVideoCanvas(it, null) }
                    boundViews.remove(uid)
                    mutableState.update { it.copy(peers = it.peers - uid) }
                }
                override fun onUserPublishStreamVideo(streamId: String, info: StreamInfo, published: Boolean) = dispatch(epoch) {
                    if (!info.isScreen) {
                        peer(info.userId, streamId, video = published)
                        if (published) {
                            callRoom.setRemoteVideoConfig(streamId, RemoteVideoConfig(320, 180, 15))
                        } else {
                            boundViews.remove(info.userId)
                            rtc.setRemoteVideoCanvas(streamId, null)
                        }
                    }
                }
                override fun onUserPublishStreamAudio(streamId: String, info: StreamInfo, published: Boolean) = dispatch(epoch) {
                    if (!info.isScreen) peer(info.userId, streamId, audio = published)
                }
                override fun onTokenWillExpire() = dispatch(epoch, renew)
                override fun onPublishPrivilegeTokenWillExpire() = dispatch(epoch, renew)
                override fun onSubscribePrivilegeTokenWillExpire() = dispatch(epoch, renew)
                override fun onNetworkQuality(local: NetworkQualityStats, remote: Array<out NetworkQualityStats>) = dispatch(epoch) {
                    mutableState.update { it.copy(rttMs = local.rtt, weakNetwork = local.txQuality >= 4 || local.rxQuality >= 4) }
                }
            }))
            // Visible membership, manual publication, automatic subscription. No capture on entry.
            checkCode(callRoom.joinRoom(token.token, UserInfo(token.user_id, ""), true,
                RTCRoomConfig(ChannelProfile.CHANNEL_PROFILE_CHAT_ROOM, false, false, true, true)))
            main.postDelayed({
                if (generation == epoch && mutableState.value.phase == ClassroomCallPhase.CONNECTING) {
                    fail("连接课堂超时，请检查网络后重试")
                }
            }, 20_000)
        } catch (_: Exception) { fail("无法连接课堂音视频，请检查服务配置和设备权限") }
    }

    private fun peer(uid: String, stream: String, audio: Boolean? = null, video: Boolean? = null) {
        mutableState.update {
            val before = it.peers[uid] ?: ClassroomPeer(uid)
            it.copy(peers = it.peers + (uid to before.copy(streamId = stream,
                audio = audio ?: before.audio, video = video ?: before.video)))
        }
        views[uid]?.let { bindVideo(uid, it) }
    }

    fun updateToken(token: String) { checkCode(checkNotNull(room).updateToken(token)) }

    fun microphone(enabled: Boolean) {
        if (enabled && mutableState.value.phase != ClassroomCallPhase.CONNECTED) return
        val rtc = engine ?: return
        try {
            if (enabled) {
                checkCode(rtc.startAudioCapture())
                checkCode(checkNotNull(room).publishStreamAudio(true))
            } else {
                room?.publishStreamAudio(false)
                rtc.stopAudioCapture()
            }
            mutableState.update { it.copy(microphone = enabled, error = null) }
        } catch (_: Exception) {
            room?.publishStreamAudio(false); rtc.stopAudioCapture()
            mutableState.update { it.copy(microphone = false, error = "麦克风开启失败，请检查权限") }
        }
    }

    fun camera(enabled: Boolean) {
        if (enabled && mutableState.value.phase != ClassroomCallPhase.CONNECTED) return
        val rtc = engine ?: return
        try {
            if (enabled) {
                checkCode(rtc.startVideoCapture())
                checkCode(checkNotNull(room).publishStreamVideo(true))
            } else {
                room?.publishStreamVideo(false)
                rtc.stopVideoCapture()
            }
            mutableState.update { it.copy(camera = enabled, error = null) }
        } catch (_: Exception) {
            room?.publishStreamVideo(false); rtc.stopVideoCapture()
            mutableState.update { it.copy(camera = false, error = "摄像头开启失败，请检查权限或是否被其他功能占用") }
        }
    }

    fun switchCamera() {
        val next = !frontCamera
        val id = if (next) com.ss.bytertc.engine.data.CameraId.CAMERA_ID_FRONT else com.ss.bytertc.engine.data.CameraId.CAMERA_ID_BACK
        if (engine?.switchCamera(id) == 0) frontCamera = next
    }

    fun bindVideo(uid: String, view: TextureView) {
        views[uid] = view
        val rtc = engine ?: return
        val streamId = if (uid == "self") "self"
            else mutableState.value.peers[uid]?.takeIf { it.video }?.streamId ?: return
        val previous = boundViews[uid]
        // AndroidView.update also runs for unrelated UI/RTT changes. Rebinding
        // the same canvas can restart rendering and cause periodic flicker.
        if (previous != null && previous.first === view && previous.second == streamId) return
        if (previous != null && previous.second != streamId && uid != "self") {
            rtc.setRemoteVideoCanvas(previous.second, null)
        }
        val canvas = VideoCanvas(view, VideoCanvas.RENDER_MODE_HIDDEN)
        val result = if (uid == "self") rtc.setLocalVideoCanvas(canvas)
            else rtc.setRemoteVideoCanvas(streamId, canvas)
        if (result == 0) boundViews[uid] = view to streamId
    }

    fun unbindVideo(uid: String, view: TextureView) {
        if (views[uid] !== view) return
        views.remove(uid)
        val previous = boundViews.remove(uid)
        if (uid == "self") engine?.setLocalVideoCanvas(null)
        else previous?.let { engine?.setRemoteVideoCanvas(it.second, null) }
    }

    private fun fail(message: String) {
        disconnect()
        mutableState.value = ClassroomCallState(phase = ClassroomCallPhase.ERROR, error = message)
    }

    fun disconnect() {
        releaseResources()
        mutableState.value = ClassroomCallState()
    }

    private fun releaseResources() {
        generation++ // Ignore callbacks from the destroyed engine, including queued leave events.
        connection.reset()
        room?.publishStreamAudio(false); room?.publishStreamVideo(false)
        engine?.stopAudioCapture(); engine?.stopVideoCapture()
        room?.leaveRoom(); room?.destroy(); room = null
        if (engine != null) RTCEngine.destroyRTCEngine()
        engine = null
        views.clear()
        boundViews.clear()
        frontCamera = true
    }

    private fun checkCode(code: Int) { check(code == 0) { "RTC operation failed: $code" } }
}
