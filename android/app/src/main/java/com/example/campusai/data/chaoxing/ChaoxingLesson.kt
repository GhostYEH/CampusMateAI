package com.example.campusai.data.chaoxing

/**
 * 作业复习课堂的可读投影。
 *
 * 服务端 stage.document 是 DSL，不是渲染结果；这里只保留学生复习需要的
 * 标题、段落、题目、提示和解析，不把原始 JSON 或隐藏答案直接铺到页面上。
 */
data class ChaoxingLesson(
    val title: String,
    val scenes: List<ChaoxingLessonScene>,
) {
    val quizCount: Int get() = scenes.count { it.questions.isNotEmpty() }

    companion object {
        fun fromDocument(document: Map<String, Any?>?): ChaoxingLesson? {
            if (document == null) return null
            val rawScenes = document["scenes"].asList() ?: return null
            val scenes = rawScenes.mapIndexedNotNull { index, raw ->
                parseScene(raw, index)
            }
            if (scenes.isEmpty()) return null
            val stage = document["stage"].asMap()
            val title = stage?.get("name").asText()
                ?: document["title"].asText()
                ?: "作业复习课堂"
            return ChaoxingLesson(title = title, scenes = scenes)
        }

        private fun parseScene(raw: Any?, index: Int): ChaoxingLessonScene? {
            val scene = raw.asMap() ?: return null
            val content = scene["content"].asMap()
            val type = scene["type"].asText()
                ?: content?.get("type").asText()
                ?: "slide"
            val title = scene["title"].asText()
                ?: content?.get("title").asText()
                ?: "第 ${index + 1} 页"
            return when (type) {
                "quiz" -> ChaoxingLessonScene(
                    id = scene["id"].asText() ?: "scene-$index",
                    title = title,
                    kind = type,
                    order = scene["order"].asInt() ?: index,
                    questions = parseQuestions(content),
                )
                "slide" -> {
                    val slide = content?.get("slide").asMap()
                    ChaoxingLessonScene(
                        id = scene["id"].asText() ?: "scene-$index",
                        title = title,
                        kind = type,
                        order = scene["order"].asInt() ?: index,
                        blocks = parseBlocks(slide ?: content),
                        body = slide?.get("body").asText() ?: content?.get("body").asText(),
                    )
                }
                else -> ChaoxingLessonScene(
                    id = scene["id"].asText() ?: "scene-$index",
                    title = title,
                    kind = type,
                    order = scene["order"].asInt() ?: index,
                    body = content?.get("html").asText()
                        ?: content?.get("body").asText()
                        ?: "这一页需要在线课堂交互能力，当前原生阅读器只展示文字与题目。",
                )
            }
        }

        private fun parseBlocks(source: Map<String, Any?>?): List<ChaoxingLessonBlock> {
            if (source == null) return emptyList()
            val sections = source["sections"].asList()
            if (sections != null) {
                return sections.mapNotNull { raw ->
                    val section = raw.asMap() ?: return@mapNotNull null
                    val heading = section["heading"].asText()
                    val bullets = section["bullets"].asList()?.mapNotNull { it.asText() }.orEmpty()
                    if (heading == null && bullets.isEmpty()) null
                    else ChaoxingLessonBlock(heading = heading, bullets = bullets)
                }
            }
            val bullets = source["bullets"].asList()?.mapNotNull { it.asText() }.orEmpty()
            return if (bullets.isEmpty()) emptyList()
            else listOf(ChaoxingLessonBlock(heading = null, bullets = bullets))
        }

        private fun parseQuestions(content: Map<String, Any?>?): List<ChaoxingLessonQuestion> {
            val raw = content?.get("questions").asList() ?: return emptyList()
            return raw.mapIndexedNotNull { index, item ->
                val question = item.asMap() ?: return@mapIndexedNotNull null
                val prompt = question["question"].asText()
                    ?: question["stem"].asText()
                    ?: return@mapIndexedNotNull null
                val options = question["options"].asList()?.mapIndexedNotNull { optionIndex, optionRaw ->
                    when (optionRaw) {
                        is String -> ChaoxingLessonOption(
                            label = optionRaw,
                            value = optionValueFromLabel(optionRaw, optionIndex),
                        )
                        else -> optionRaw.asMap()?.let { map ->
                            val label = map["label"].asText() ?: map["text"].asText()
                            val value = map["value"].asText() ?: label
                            if (label == null || value == null) null
                            else ChaoxingLessonOption(label = label, value = value)
                        }
                    }
                }.orEmpty()
                val answer = when (val rawAnswer = question["answer"]) {
                    is String -> listOf(rawAnswer)
                    else -> rawAnswer.asList()?.mapNotNull { it.asText() }.orEmpty()
                }
                val role = question["exerciseRole"].asText() ?: question["exercise_role"].asText()
                val sourceNumber = question["sourceQuestionNumber"].asInt()
                    ?: question["source_question_number"].asInt()
                ChaoxingLessonQuestion(
                    id = question["id"].asText() ?: "question-$index",
                    type = question["type"].asText() ?: "short_answer",
                    prompt = prompt,
                    options = options,
                    answer = answer,
                    analysis = question["analysis"].asText()
                        ?: question["explanation"].asText()
                        ?: "暂无解析。",
                    hints = question["hints"].asList()?.mapNotNull { it.asText() }.orEmpty(),
                    exerciseRole = role,
                    sourceNumber = sourceNumber,
                )
            }
        }

        private fun optionValueFromLabel(label: String, index: Int): String {
            val prefix = label.substringBefore('.', missingDelimiterValue = "").trim()
            return if (prefix.length == 1 && prefix[0].isLetter()) prefix
            else ('A' + index).toString()
        }
    }
}

data class ChaoxingLessonScene(
    val id: String,
    val title: String,
    val kind: String,
    val order: Int,
    val blocks: List<ChaoxingLessonBlock> = emptyList(),
    val questions: List<ChaoxingLessonQuestion> = emptyList(),
    val body: String? = null,
)

data class ChaoxingLessonBlock(
    val heading: String?,
    val bullets: List<String>,
)

data class ChaoxingLessonOption(
    val label: String,
    val value: String,
)

data class ChaoxingLessonQuestion(
    val id: String,
    val type: String,
    val prompt: String,
    val options: List<ChaoxingLessonOption>,
    val answer: List<String>,
    val analysis: String,
    val hints: List<String>,
    val exerciseRole: String?,
    val sourceNumber: Int?,
) {
    val isMultiple: Boolean get() = type == "multiple"
    val isChoice: Boolean get() = options.isNotEmpty() && type != "short_answer"
    val roleLabel: String
        get() = when (exerciseRole) {
            "transfer" -> "变式练习"
            "retry" -> "原题重做"
            else -> "练习"
        }
}

// JSON maps from Moshi/Runtime use LinkedHashMap and nested Any values. These
// helpers keep the parser independent from Android so it can be unit-tested.
private fun Any?.asMap(): Map<String, Any?>? {
    val value = this as? Map<*, *> ?: return null
    return value.entries.associate { (key, item) -> key.toString() to item }
}

private fun Any?.asList(): List<Any?>? = this as? List<*>
private fun Any?.asText(): String? = when (this) {
    is String -> takeIf { it.isNotBlank() }
    is Number -> toString()
    else -> null
}

private fun Any?.asInt(): Int? = when (this) {
    is Number -> toInt()
    is String -> toIntOrNull()
    else -> null
}
