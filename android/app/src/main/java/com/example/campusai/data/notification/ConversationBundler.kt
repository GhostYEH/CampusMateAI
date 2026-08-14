package com.example.campusai.data.notification

import java.security.MessageDigest

data class QueuedNotification(
    val id: Long,
    val fingerprint: String,
    val source: NotificationSource,
    val normalizedGroupName: String,
    val text: String,
    val publishedAt: Long,
    val attemptCount: Int = 0,
)

data class ConversationBundle(
    val clientId: String,
    val clientFingerprint: String,
    val source: NotificationSource,
    val normalizedGroupName: String,
    val notificationIds: List<Long>,
    val messages: List<QueuedNotification>,
) {
    val content: String = messages.joinToString("\n") { it.text }.take(ConversationBundler.BATCH_MAX_CHARS)
    val maxAttemptCount: Int = messages.maxOfOrNull { it.attemptCount } ?: 0
}

object ConversationBundler {
    const val BATCH_QUIET_WINDOW_MS = 20_000L
    const val BATCH_MAX_MESSAGES = 20
    const val BATCH_MAX_CHARS = 4_000
    const val BATCH_MAX_AGE_MS = 90_000L

    fun bundle(rows: List<QueuedNotification>): List<ConversationBundle> = rows
        .sortedBy { it.publishedAt }
        .groupBy { it.source to GroupNameNormalizer.normalize(it.normalizedGroupName).orEmpty() }
        .flatMap { (key, groupRows) -> splitGroup(key.first, key.second, groupRows) }
        .sortedBy { it.messages.firstOrNull()?.publishedAt ?: Long.MAX_VALUE }

    private fun splitGroup(
        source: NotificationSource,
        group: String,
        rows: List<QueuedNotification>,
    ): List<ConversationBundle> {
        val result = mutableListOf<ConversationBundle>()
        var current = mutableListOf<QueuedNotification>()
        var chars = 0
        fun flush() {
            if (current.isEmpty()) return
            val fingerprints = current.joinToString("\u001F") { it.fingerprint }
            val digest = MessageDigest.getInstance("SHA-256").digest(fingerprints.toByteArray())
                .joinToString("") { "%02x".format(it) }
            result += ConversationBundle(
                clientId = "${source.name}:${group}:${current.first().id}",
                clientFingerprint = digest,
                source = source,
                normalizedGroupName = group,
                notificationIds = current.map { it.id },
                messages = current.toList(),
            )
            current = mutableListOf()
            chars = 0
        }
        rows.forEach { row ->
            val gap = if (current.isEmpty()) 0 else row.publishedAt - current.last().publishedAt
            val age = if (current.isEmpty()) 0 else row.publishedAt - current.first().publishedAt
            if (current.isNotEmpty() && (gap > BATCH_QUIET_WINDOW_MS || age > BATCH_MAX_AGE_MS ||
                    current.size >= BATCH_MAX_MESSAGES || chars + row.text.length + 1 > BATCH_MAX_CHARS)) flush()
            current += row
            chars += row.text.length + 1
        }
        flush()
        return result
    }
}
