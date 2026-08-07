package com.example.campusai.services

import com.example.campusai.data.repository.AppRepository
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import java.security.MessageDigest
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.app.Application

/**
 * 微信通知监听服务。
 *
 * 监听来自微信的通知，过滤群聊消息，并根据用户配置的关键词进行处理。
 */
class WeChatNoticeListenerService : NotificationListenerService() {

    private lateinit var appRepository: AppRepository
    private val serviceScope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // 简单的文本哈希缓存，用于避免短时间内重复处理同一条通知
    private val recentNotificationHashes = LinkedHashMap<String, Long>()

    override fun onCreate() {
        super.onCreate()
        appRepository = AppRepository(applicationContext as Application)
    }

    /**
     * 当有新通知发布时调用。
     */
    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        super.onNotificationPosted(sbn)

        if (sbn?.packageName != "com.tencent.mm") {
            return // 只处理微信通知
        }

        val notification = sbn.notification ?: return
        val extras = notification.extras

        val title = extras.getString("android.title") ?: ""
        var content = ""

        val bigText = extras.getCharSequence("android.bigText")?.toString()
        val textLines = extras.getCharSequenceArray("android.textLines")?.joinToString("\n")
        val androidText = extras.getCharSequence("android.text")?.toString()

        val template = extras.getString("android.template")
        if (template == "android.app.Notification\$MessagingStyle") {
            val messages = extras.getParcelableArray("android.messages")
            if (messages != null && messages.isNotEmpty()) {
                val lastMessage = messages.last() as? android.os.Bundle
                val msgText = lastMessage?.getCharSequence("text")?.toString()
                if (!msgText.isNullOrBlank()) {
                    content = msgText
                }
            }
        }

        if (content.isBlank()) {
            content = bigText ?: textLines ?: androidText ?: ""
        }

        if (title.isBlank() || content.isBlank()) {
            return // 忽略没有标题或内容的通知
        }

        serviceScope.launch {
            val monitoredGroups = appRepository.getMonitoredGroupChats().first()
            val matchedGroup = monitoredGroups.find { title.contains(it) }

            if (matchedGroup != null) {
                // 移除类似 "SenderName: " 的前缀
                val colonIndex = content.indexOf(": ")
                val cleanContent = if (colonIndex != -1 && colonIndex < 15) {
                    content.substring(colonIndex + 2)
                } else {
                    content
                }

                if (looksLikeNotice(cleanContent)) {
                    if (isDuplicate(cleanContent, matchedGroup)) return@launch

                    appRepository.enqueueNoticeIngestion(
                        content = cleanContent,
                        sourceName = matchedGroup, // 使用配置的确切群名，而不是原始 title
                        publishedAt = java.time.Instant.now().toString()
                    )
                }
            }
        }
    }

    /**
     * 检查文本是否像一个通知。
     *
     * 移植自后端 `_looks_like_notice` 函数的逻辑。
     */
    private fun looksLikeNotice(text: String): Boolean {
        if (text.isBlank() || text.length < 5) {
            return false
        }
        val signals = listOf("请", "通知", "前", "截止", "提交", "报名", "申请", "截至", "同学")
        return signals.any { text.contains(it) }
    }

    /**
     * 使用文本哈希去重，避免同一条通知被微信多次刷新重复入库。
     */
    private fun isDuplicate(content: String, groupName: String): Boolean {
        val dedupKey = "wechat_${groupName}_$content"
        val hash = dedupKey.toSha256()
        val now = System.currentTimeMillis()

        // 清理超过5分钟的旧哈希
        recentNotificationHashes.entries.removeIf { (_, timestamp) ->
            now - timestamp > 5 * 60 * 1000
        }

        return if (recentNotificationHashes.containsKey(hash)) {
            true
        } else {
            recentNotificationHashes[hash] = now
            false
        }
    }

    private fun String.toSha256(): String {
        val bytes = MessageDigest.getInstance("SHA-256").digest(this.toByteArray())
        return bytes.joinToString("") { "%02x".format(it) }
    }
}
