package com.example.campusai.data.classroom.nativeplayer

import java.util.Locale

/**
 * 幻灯片文本是带内联样式的 HTML。这里只做展示层需要的无损降级：
 * 保留换行、列表符号和字号/颜色/粗体/斜体/下划线/对齐，丢掉不生效的标签。
 * 任何未知标签都只去掉标记，不丢正文。
 */
data class NativeHtmlText(
    val plainText: String,
    val fontSize: Double?,
    val color: String?,
    val bold: Boolean,
    val italic: Boolean,
    val underline: Boolean,
    val align: String,
)

object NativeClassroomText {

    // 正文也会直接包含不等式。只剥去带有合法名称和属性的 HTML 标记。
    private val tagRegex = Regex(
        """<!--[\s\S]*?-->|</?[A-Za-z][A-Za-z0-9:-]*(?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s"'=<>]+))*\s*/?>""",
    )
    private val brRegex = Regex("(?i)<br\\s*/?>")
    private val blockEndRegex = Regex("(?i)</(p|div|h[1-6]|tr)>")
    private val listItemEndRegex = Regex("(?i)</li>")
    private val listItemStartRegex = Regex("(?i)<li(?:\\s[^<>]*)?>")
    private val fontSizeRegex = Regex("(?i)font-size\\s*:\\s*([0-9.]+)\\s*px")
    private val colorRegex = Regex("(?i)(?<![-a-z])color\\s*:\\s*(#[0-9a-f]{3,8}|rgba?\\([^)]*\\))")
    private val weightRegex = Regex("(?i)font-weight\\s*:\\s*(bold|[6-9]00)")
    private val italicRegex = Regex("(?i)font-style\\s*:\\s*italic")
    private val underlineRegex = Regex("(?i)text-decoration[^;]*underline")
    private val alignRegex = Regex("(?i)text-align\\s*:\\s*(left|center|right|justify)")
    private val boldTagRegex = Regex("(?i)<(b|strong)[^>]*>")
    private val italicTagRegex = Regex("(?i)<(i|em)[^>]*>")
    private val multiSpaceRegex = Regex("[ \\t]+")
    private val multiNewlineRegex = Regex("\\n{3,}")

    fun parse(
        html: String,
        fallbackColor: String? = null,
        fallbackFontSize: Double? = null,
        fallbackBold: Boolean = false,
        fallbackAlign: String = "left",
    ): NativeHtmlText {
        val fontSize = fontSizeRegex.find(html)?.groupValues?.getOrNull(1)?.toDoubleOrNull()
            ?: fallbackFontSize
        val color = colorRegex.find(html)?.groupValues?.getOrNull(1)?.takeIf { it.isNotBlank() }
            ?: fallbackColor
        val bold = fallbackBold || weightRegex.containsMatchIn(html) || boldTagRegex.containsMatchIn(html)
        val italic = italicRegex.containsMatchIn(html) || italicTagRegex.containsMatchIn(html)
        val underline = underlineRegex.containsMatchIn(html)
        val align = alignRegex.find(html)?.groupValues?.getOrNull(1)
            ?.lowercase(Locale.ROOT)
            ?: fallbackAlign

        val plain = html
            .replace(brRegex, "\n")
            .replace(listItemEndRegex, "\n")
            .replace(listItemStartRegex, "• ")
            .replace(blockEndRegex, "\n")
            .replace(tagRegex, "")
            .let(::decodeEntities)
            .replace(multiSpaceRegex, " ")
            .replace(multiNewlineRegex, "\n\n")
            .trim()

        return NativeHtmlText(
            plainText = plain.ifBlank { stripSimple(html) },
            fontSize = fontSize,
            color = color,
            bold = bold,
            italic = italic,
            underline = underline,
            align = align,
        )
    }

    fun stripSimple(html: String): String = html
        .replace(brRegex, "\n")
        .replace(tagRegex, "")
        .let(::decodeEntities)
        .trim()

    /** 课件元素顺序保留同一小节的标题、正文与公式。 */
    fun lectureParagraphs(slide: NativeSlide): List<String> = slide.elements.asSequence()
        .filter { it.opacity > 0.0 }
        .mapNotNull { element ->
            when (element) {
                is NativeCanvasElement.Text -> element.plainText
                is NativeCanvasElement.Latex -> readableFormula(element.latex)
                else -> null
            }
        }
        .flatMap { it.lineSequence() }
        .map { it.trim().removePrefix("•").trim() }
        .filter { it.any(Char::isLetterOrDigit) }
        .toList()

    fun forSpeech(text: String): String = text
        .replace("≤", "小于等于").replace("≥", "大于等于")
        .replace("<", "小于").replace(">", "大于").replace("=", "等于")
        .replace("²", "的平方").replace("³", "的立方").replace("∞", "无穷大")

    /** 无 MathJax 时也能读的公式降级：保留结构、替换常见符号。 */
    fun readableFormula(raw: String): String {
        var text = raw.trim()
            .removePrefix("$$").removeSuffix("$$")
            .removePrefix("$").removeSuffix("$")
            .removePrefix("\\[").removeSuffix("\\]")
            .removePrefix("\\(").removeSuffix("\\)")
        text = Regex("\\\\frac\\{([^{}]*)\\}\\{([^{}]*)\\}").replace(text, "($1)/($2)")
        text = Regex("\\\\sqrt\\{([^{}]*)\\}").replace(text, "√($1)")
        text = Regex("\\^\\{([^{}]*)\\}").replace(text, "^($1)")
        text = Regex("_\\{([^{}]*)\\}").replace(text, "_($1)")
        text = Regex("\\^([0-9]+)").replace(text) { match ->
            superscript(match.groupValues[1])
        }
        val symbols = mapOf(
            "\\\\times" to "×",
            "\\\\div" to "÷",
            "\\\\cdot" to "·",
            "\\\\leq?" to "≤",
            "\\\\geq?" to "≥",
            "\\\\neq?" to "≠",
            "\\\\pm" to "±",
            "\\\\pi" to "π",
            "\\\\alpha" to "α",
            "\\\\beta" to "β",
            "\\\\gamma" to "γ",
            "\\\\delta" to "δ",
            "\\\\theta" to "θ",
            "\\\\lambda" to "λ",
            "\\\\mu" to "μ",
            "\\\\sigma" to "σ",
            "\\\\omega" to "ω",
            "\\\\infty" to "∞",
            "\\\\rightarrow" to "→",
            "\\\\leftarrow" to "←",
            "\\\\sum" to "Σ",
            "\\\\int" to "∫",
        )
        symbols.forEach { (pattern, replacement) ->
            text = Regex(pattern).replace(text, replacement)
        }
        text = Regex("\\\\[a-zA-Z]+").replace(text) { match ->
            match.value.removePrefix("\\")
        }
        return text.replace(Regex("[{}]"), "").trim()
    }

    private fun superscript(digits: String): String {
        val map = mapOf(
            '0' to '⁰', '1' to '¹', '2' to '²', '3' to '³', '4' to '⁴',
            '5' to '⁵', '6' to '⁶', '7' to '⁷', '8' to '⁸', '9' to '⁹',
        )
        return digits.map { map[it] ?: it }.joinToString("")
    }

    private fun decodeEntities(value: String): String {
        var text = value
            .replace("&nbsp;", " ")
            .replace("&amp;", "&")
            .replace("&lt;", "<")
            .replace("&gt;", ">")
            .replace("&quot;", "\"")
            .replace("&#39;", "'")
            .replace("&apos;", "'")
            .replace("&mdash;", "—")
            .replace("&ndash;", "–")
            .replace("&hellip;", "…")
        text = Regex("&#x([0-9a-fA-F]+);").replace(text) { match ->
            runCatching { match.groupValues[1].toInt(16).toChar().toString() }.getOrDefault(match.value)
        }
        text = Regex("&#([0-9]+);").replace(text) { match ->
            runCatching { match.groupValues[1].toInt().toChar().toString() }.getOrDefault(match.value)
        }
        return text
    }
}
