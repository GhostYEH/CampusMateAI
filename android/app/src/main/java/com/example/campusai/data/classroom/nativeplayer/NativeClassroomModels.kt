package com.example.campusai.data.classroom.nativeplayer

import java.io.Serializable

/**
 * 受管课堂的原生播放模型。
 *
 * 这里刻意不依赖 Compose、Android 或网络：文档解析、播放决定、奖励结算和
 * 缓存键都能在 JVM 单元测试里直接跑。界面层只消费这些不可变快照。
 */

enum class NativeClassroomSource {
    MANAGED,
    COURSE_CLASSIC,
    SELF_CLASSIC,
}

data class NativeClassroomRef(
    val courseId: String,
    val workspaceId: String,
    val stageId: String,
    val title: String = "",
    val workspaceName: String = "",
    /** 旧网页入口只作为兼容路径；受管课堂没有可信 URL 时保持 null。 */
    val webFallbackUrl: String? = null,
    /** 经典课堂与自主选题课堂的会话标识；受管课堂为 null。 */
    val sessionId: String? = null,
    val classroomId: String? = null,
    val source: NativeClassroomSource = NativeClassroomSource.MANAGED,
) : Serializable {
    /** 学习记录与奖励的稳定身份，不随 revision 变化。 */
    val identityUrl: String
        get() {
            if (source == NativeClassroomSource.MANAGED) {
                return "campusmate://magicclass/$courseId/$workspaceId/$stageId"
            }
            // 有可信网页地址时沿用旧 WebView 的记录指纹，原生/兼容切换不重复计一次课。
            val webIdentity = webFallbackUrl?.takeIf { it.isNotBlank() }
            if (webIdentity != null) return webIdentity
            return when (source) {
                NativeClassroomSource.COURSE_CLASSIC ->
                    "campusmate://magicclass/$courseId/classic/${sessionId.orEmpty()}"
                NativeClassroomSource.SELF_CLASSIC ->
                    "campusmate://magicclass/self/${sessionId.orEmpty()}"
                NativeClassroomSource.MANAGED -> ""
            }
        }

    val stableKey: String
        get() = when (source) {
            NativeClassroomSource.MANAGED -> "$courseId:$workspaceId:$stageId"
            NativeClassroomSource.COURSE_CLASSIC -> "classic:$courseId:${sessionId.orEmpty()}"
            NativeClassroomSource.SELF_CLASSIC -> "self:${sessionId.orEmpty()}"
        }
}

enum class NativeRenderKind {
    NATIVE,
    SANDBOX_HTML,
    SANDBOX_URL,
    UNSUPPORTED,
    MISSING,
}

data class NativePlaybackStep(
    val actionId: String,
    val type: String,
    val mode: String = "sync",
) {
    val blocking: Boolean get() = mode != "fire_and_forget"
}

data class NativeScenePlan(
    val id: String,
    val type: String,
    val title: String,
    val order: Int,
    val renderKind: NativeRenderKind,
    val sandbox: String = "",
    /** 沙箱 HTML 正文或受限 URL；与 sandbox 权限字符串分开，避免把权限当内容渲染。 */
    val sandboxPayload: String = "",
    val widgetType: String? = null,
    val renderReason: String? = null,
    val steps: List<NativePlaybackStep> = emptyList(),
    val droppedActions: List<String> = emptyList(),
    val whiteboards: Int = 0,
    val multiAgent: Boolean = false,
) {
    val isNative: Boolean get() = renderKind == NativeRenderKind.NATIVE
    val isSandbox: Boolean
        get() = renderKind == NativeRenderKind.SANDBOX_HTML || renderKind == NativeRenderKind.SANDBOX_URL
}

data class NativePlaybackPlan(
    val stageId: String,
    val workspaceId: String,
    val title: String,
    val revision: Int,
    val dslVersion: String = "",
    val startIndex: Int = 0,
    val scenes: List<NativeScenePlan> = emptyList(),
    val degraded: List<String> = emptyList(),
) {
    val hasScenes: Boolean get() = scenes.isNotEmpty()
}

// 画布

data class NativeSlideTheme(
    val backgroundColor: String? = null,
    val fontColor: String? = null,
    val fontName: String? = null,
)

data class NativeSlideBackground(
    val color: String? = null,
    val imageUrl: String? = null,
    val gradientColors: List<String> = emptyList(),
)

data class NativeSlide(
    val id: String,
    val viewportSize: Double = 1000.0,
    val viewportRatio: Double = 9.0 / 16.0,
    val theme: NativeSlideTheme = NativeSlideTheme(),
    val background: NativeSlideBackground = NativeSlideBackground(),
    val elements: List<NativeCanvasElement> = emptyList(),
) {
    val aspectRatio: Float
        get() = (1.0 / viewportRatio).toFloat().takeIf { it > 0f } ?: (16f / 9f)
}

sealed class NativeCanvasElement {
    abstract val id: String
    abstract val left: Double
    abstract val top: Double
    abstract val width: Double
    abstract val height: Double
    abstract val rotate: Double
    abstract val opacity: Double

    data class Text(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val html: String,
        val plainText: String,
        val fontColor: String?,
        val fontSize: Double?,
        val bold: Boolean,
        val italic: Boolean,
        val underline: Boolean,
        val align: String,
        val verticalAlign: String,
        val lineHeight: Double,
        val textType: String?,
    ) : NativeCanvasElement()

    data class Shape(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val shapeType: String,
        val fill: String?,
        val stroke: String?,
        val strokeWidth: Double,
        val radius: Double,
    ) : NativeCanvasElement()

    data class Line(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val startX: Double,
        val startY: Double,
        val endX: Double,
        val endY: Double,
        val color: String?,
        val strokeWidth: Double,
    ) : NativeCanvasElement()

    data class Image(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val source: String,
        val radius: Double,
    ) : NativeCanvasElement()

    data class Video(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val source: String,
        val poster: String?,
    ) : NativeCanvasElement()

    data class Table(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val rows: List<NativeTableCellRow>,
        val columnWeights: List<Double>,
        val rowHeights: List<Double>,
        val borderColor: String?,
        val headerFill: String?,
        val textColor: String?,
    ) : NativeCanvasElement()

    data class Chart(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val chartType: String,
        val labels: List<String>,
        val series: List<List<Double>>,
        val colors: List<String>,
        val textColor: String?,
        val lineColor: String?,
    ) : NativeCanvasElement()

    data class Latex(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val latex: String,
        val color: String?,
        val fontSize: Double?,
    ) : NativeCanvasElement()

    data class Audio(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val source: String,
    ) : NativeCanvasElement()

    data class Unknown(
        override val id: String,
        override val left: Double,
        override val top: Double,
        override val width: Double,
        override val height: Double,
        override val rotate: Double,
        override val opacity: Double,
        val type: String,
    ) : NativeCanvasElement()
}

data class NativeTableCellRow(val cells: List<NativeTableCell>)

data class NativeTableCell(
    val text: String,
    val colspan: Int = 1,
    val rowspan: Int = 1,
    val bold: Boolean = false,
    val align: String = "left",
    val fill: String? = null,
    val color: String? = null,
)
