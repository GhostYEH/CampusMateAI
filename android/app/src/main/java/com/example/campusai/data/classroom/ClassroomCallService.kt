package com.example.campusai.data.classroom

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.example.campusai.MainActivity
import com.example.campusai.R

/** Keeps an ongoing call audible with the screen locked; camera stays foreground-only. */
class ClassroomCallService : Service() {
    private var ownedEpoch = -1L
    override fun onCreate() {
        super.onCreate()
        getSystemService(NotificationManager::class.java).createNotificationChannel(
            NotificationChannel(CHANNEL, "课堂通话", NotificationManager.IMPORTANCE_LOW),
        )
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == END) {
            lease.stop(intent.getLongExtra(EPOCH, -1L))
            if (!lease.hasOwner) stopSelf()
            return START_NOT_STICKY
        }
        val requestedEpoch = intent?.getLongExtra(EPOCH, -1L) ?: -1L
        if (!lease.isCurrent(requestedEpoch)) {
            if (!lease.hasOwner) stopSelf(startId)
            return START_NOT_STICKY
        }
        ownedEpoch = requestedEpoch
        val open = PendingIntent.getActivity(this, 0,
            Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val end = PendingIntent.getService(this, 1, Intent(this, ClassroomCallService::class.java).setAction(END).putExtra(EPOCH, requestedEpoch), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("共同课堂通话中")
            .setContentText("点击返回应用；可随时断开通话")
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(0, "断开通话", end)
            .build()
        var types = ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R && intent?.getBooleanExtra(MIC, false) == true) {
            types = types or ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
        }
        try {
            ServiceCompat.startForeground(this, NOTIFICATION_ID, notification, types)
            lease.ready(requestedEpoch)
        } catch (_: Exception) {
            lease.stop(requestedEpoch)
            if (!lease.hasOwner) stopSelf()
        }
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        // A queued destroy from an earlier call must not hang up a new call.
        lease.stop(ownedEpoch)
        super.onDestroy()
    }
    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val CHANNEL = "classroom_call"
        private const val NOTIFICATION_ID = 4701
        private const val END = "classroom.end"
        private const val MIC = "microphone"
        private const val EPOCH = "call_epoch"
        private val lease = ClassroomServiceLease()
        fun start(context: Context, owner: Any, microphone: Boolean, onStop: () -> Unit, onReady: () -> Unit) {
            val generation = lease.claim(owner, onStop, onReady)
            try {
                ContextCompat.startForegroundService(context, Intent(context, ClassroomCallService::class.java).putExtra(MIC, microphone).putExtra(EPOCH, generation))
            } catch (error: Exception) {
                lease.stop(generation)
                throw error
            }
        }
        fun stop(context: Context, owner: Any) {
            if (lease.release(owner)) context.stopService(Intent(context, ClassroomCallService::class.java))
        }
    }
}
