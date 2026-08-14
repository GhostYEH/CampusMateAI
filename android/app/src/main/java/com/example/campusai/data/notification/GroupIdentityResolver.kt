package com.example.campusai.data.notification

/** Produces group-name candidates in descending confidence order. */
object GroupIdentityResolver {
    fun candidates(notification: CapturedNotification): List<String> = buildList {
        GroupNameNormalizer.normalize(notification.conversationTitle)?.let(::add)
        GroupNameNormalizer.normalize(notification.summaryText)?.let(::add)
        GroupNameNormalizer.normalize(notification.subText)?.let(::add)
        GroupNameNormalizer.normalize(notification.title)?.let(::add)
    }.distinct()

    fun matchingGroup(notification: CapturedNotification, whitelist: Set<String>): String? =
        candidates(notification).firstOrNull { GroupNameNormalizer.matches(it, whitelist) }
}
