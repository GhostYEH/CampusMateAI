package com.example.campusai.data.notification

import java.text.Normalizer

/** Normalizes only presentation artifacts; matching remains exact. */
object GroupNameNormalizer {
    private val counterSuffixes = listOf(
        Regex("\\s*[（(]\\s*\\d+\\s*条?(?:新)?消息\\s*[）)]\\s*$"),
        Regex("\\s*[（(]\\s*\\d+\\s*[）)]\\s*$"),
        Regex("\\s+\\d+\\s*条(?:新)?消息\\s*$"),
    )

    fun normalize(value: String?): String? {
        var normalized = value?.trim()?.takeIf { it.isNotEmpty() } ?: return null
        normalized = Normalizer.normalize(normalized, Normalizer.Form.NFKC)
            .replace(Regex("[\\t\\r\\n ]+"), " ")
            .trim()
        counterSuffixes.forEach { normalized = normalized.replace(it, "").trim() }
        return normalized.takeIf { it.isNotEmpty() }
    }

    fun matches(candidate: String?, whitelist: Set<String>): Boolean {
        val normalizedCandidate = normalize(candidate) ?: return false
        return whitelist.asSequence().mapNotNull(::normalize).any { it == normalizedCandidate }
    }
}
