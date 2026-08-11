package com.example.campusai.data.notification

object NotificationTextSanitizer {
    fun clean(value: CharSequence?): String? = value
        ?.toString()
        ?.replace(Regex("\\s+"), " ")
        ?.trim()
        ?.takeIf(String::isNotEmpty)

    fun primaryText(bigText: CharSequence?, text: CharSequence?): String? =
        clean(bigText) ?: clean(text)

    fun joinedLines(lines: Array<CharSequence>?): String? = lines
        ?.mapNotNull(::clean)
        ?.distinct()
        ?.joinToString("\n")
        ?.takeIf(String::isNotEmpty)
}
