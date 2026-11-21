package com.example.campusai.data.classroom.nativeplayer

// 场景、文档、测验、PBL、动作与页面状态。

data class NativeScene(
    val id: String,
    val stageId: String,
    val title: String,
    val type: String,
    val order: Int,
    val content: Map<String, Any?>,
    val actions: List<NativeAction> = emptyList(),
    val whiteboards: List<NativeSlide> = emptyList(),
    val multiAgent: Boolean = false,
)

/**
 * 解析后的完整课堂：`scenes` 按 order 排序，包含每页真实正文。
 * 各类型的投影在解析时一次性算好，避免 Compose 重组时反复遍历动态 Map。
 */
data class NativeStageDocument(
    val stageId: String,
    val title: String,
    val revision: Int,
    val dslVersion: String = "",
    val scenes: List<NativeScene> = emptyList(),
    val slideByScene: Map<String, NativeSlide> = emptyMap(),
    val quizByScene: Map<String, NativeQuiz> = emptyMap(),
    val pblByScene: Map<String, NativePblProject> = emptyMap(),
    val interactiveByScene: Map<String, NativeInteractive> = emptyMap(),
    val whiteboard: NativeSlide? = null,
) {
    fun scene(id: String?): NativeScene? = id?.let { target -> scenes.firstOrNull { scene -> scene.id == target } }
}

data class NativeInteractive(
    val html: String? = null,
    val url: String? = null,
    val widgetType: String? = null,
    val title: String? = null,
    val description: String? = null,
)

// 测验

data class NativeQuiz(
    val questions: List<NativeQuestion> = emptyList(),
) {
    val totalPoints: Double
        get() = questions.sumOf { it.points }
}

data class NativeQuestion(
    val id: String,
    val number: Int,
    val type: String,
    val question: String,
    val options: List<NativeQuizOption> = emptyList(),
    val answerKey: List<String> = emptyList(),
    val analysis: String = "",
    val commentPrompt: String = "",
    val hasAnswer: Boolean = false,
    val points: Double = 1.0,
) {
    val isMultiple: Boolean get() = type == "multiple"
    val isShortAnswer: Boolean get() = type == "short_answer" || type == "short"
    val autoGradable: Boolean get() = !isShortAnswer && hasAnswer && answerKey.isNotEmpty()
}

data class NativeQuizOption(val label: String, val value: String)

data class NativeAnswer(
    val selected: Set<String> = emptySet(),
    val text: String = "",
) {
    val hasValue: Boolean get() = selected.isNotEmpty() || text.isNotBlank()
}

data class NativeQuizResult(
    val questionId: String,
    val correct: Boolean?,
    val earned: Double,
    val comment: String? = null,
    val selfChecked: Boolean = false,
)

// PBL

data class NativePblProject(
    val title: String,
    val description: String,
    val instructorName: String? = null,
    val milestones: List<NativePblMilestone> = emptyList(),
)

data class NativePblMilestone(
    val title: String,
    val description: String,
    val status: String,
    val tasks: List<NativePblTask> = emptyList(),
)

data class NativePblTask(
    val title: String,
    val description: String,
    val status: String,
    val hints: List<String> = emptyList(),
)

// 动作与同学

data class NativeAction(
    val id: String,
    val type: String,
    val title: String = "",
    val description: String = "",
    val elementId: String? = null,
    val color: String? = null,
    val dimOpacity: Double = 0.75,
    val durationMs: Long = 0L,
    val speech: String? = null,
    val videoUrl: String? = null,
    /** 经典课堂 speech.payload.audioUrl；有现成讲解音频时不再走系统朗读。 */
    val audioUrl: String? = null,
    val supported: Boolean = true,
    val reason: String? = null,
)

data class NativeClassmate(
    val id: String,
    val name: String,
    val role: String,
    val persona: String,
)

data class NativeClassmateMessage(
    val agentId: String,
    val text: String,
)

// 页面状态

data class NativePageState(
    val index: Int = 0,
    val total: Int = 0,
    val sceneId: String? = null,
    val progress: Float = 0f,
    val hasPrev: Boolean = false,
    val hasNext: Boolean = false,
) {
    companion object {
        fun of(scenes: List<NativeScenePlan>, index: Int): NativePageState {
            val total = scenes.size
            val safe = if (total == 0) 0 else index.coerceIn(0, total - 1)
            return NativePageState(
                index = safe,
                total = total,
                sceneId = scenes.getOrNull(safe)?.id,
                progress = if (total == 0) 0f else (safe + 1f) / total,
                hasPrev = safe > 0,
                hasNext = total > 0 && safe < total - 1,
            )
        }
    }
}
