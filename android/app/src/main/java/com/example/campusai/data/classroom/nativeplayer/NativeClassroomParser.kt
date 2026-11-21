package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.ClassroomPlaybackSceneDto
import com.example.campusai.data.remote.MagicClassScenePlaybackDto
import com.example.campusai.data.remote.MagicClassStagePlaybackDto
import com.example.campusai.data.remote.MagicClassWorkspaceStageDto
import java.util.Locale

/**
 * 把受管服务的开放 DSL 文档收敛成播放器能消费的类型。
 *
 * 关键原则：
 * - `render.kind` 是播放决定的唯一判据，客户端不自己猜；
 * - 文档里没有的东西不编造，解析失败的元素降级为 [NativeCanvasElement.Unknown]；
 * - 所有顺序以服务端 order 为准，再按索引兜底。
 */
object NativeClassroomParser {

    fun parsePlan(dto: MagicClassStagePlaybackDto): NativePlaybackPlan {
        val scenes = dto.scenes.orEmpty()
            .mapNotNull(::parseScenePlan)
            .sortedBy { it.order }
        val start = dto.startIndex.coerceIn(0, (scenes.size - 1).coerceAtLeast(0))
        return NativePlaybackPlan(
            stageId = dto.stageId,
            workspaceId = dto.workspaceId,
            title = dto.title.ifBlank { "课堂" },
            revision = dto.revision,
            dslVersion = dto.dslVersion.orEmpty(),
            startIndex = start,
            scenes = scenes,
            degraded = dto.degraded.orEmpty().mapNotNull { degradeLabel(it) },
        )
    }

    fun parseStage(dto: MagicClassWorkspaceStageDto): NativeStageDocument =
        parseDocument(
            document = dto.document.orEmpty(),
            stageId = dto.id,
            fallbackTitle = dto.title.orEmpty(),
            revision = dto.revision,
            dslVersion = dto.dslVersion.orEmpty(),
        )

    /**
     * 经典课堂/自主选题的 playback 已经带每个 scene 的完整 content；不需要再请求
     * stage。这里只把它投影成与受管课堂相同的文档模型，渲染和奖励逻辑保持一套。
     */
    fun parsePlayback(dto: ClassroomPlaybackDto): NativeStageDocument {
        val stageId = dto.classroomId.ifBlank { dto.sessionId }.ifBlank { "classic" }
        val scenes = dto.scenes.mapIndexed { index, scene ->
            val content = scene.content.orEmpty().toMutableMap()
            linkedMapOf<String, Any?>(
                "id" to scene.id.ifBlank { "scene_$index" },
                "type" to scene.type.ifBlank { "unknown" },
                "title" to scene.title.ifBlank { "第 ${index + 1} 页" },
                "order" to scene.order,
                "content" to content,
                "actions" to scene.actions.map(::flattenPlaybackAction),
                "whiteboards" to emptyList<Any>(),
                "multiAgent" to scene.multiAgent,
            )
        }
        return parseDocument(
            document = mapOf(
                "stage" to linkedMapOf<String, Any?>("title" to dto.title),
                "scenes" to scenes,
            ),
            stageId = stageId,
            fallbackTitle = dto.title,
            revision = revisionOf(dto.contentVersion.ifBlank { dto.generatedAt }),
            dslVersion = dto.contractVersion,
        )
    }

    fun parsePlaybackPlan(dto: ClassroomPlaybackDto): NativePlaybackPlan {
        val scenes = dto.scenes
            .mapIndexedNotNull { index, scene -> parseClassicScenePlan(scene, index) }
            .sortedBy { it.order }
        val start = dto.startIndex.coerceIn(0, (scenes.size - 1).coerceAtLeast(0))
        return NativePlaybackPlan(
            stageId = dto.classroomId.ifBlank { dto.sessionId },
            workspaceId = dto.courseId,
            title = dto.title.ifBlank { "课堂" },
            revision = revisionOf(dto.contentVersion.ifBlank { dto.generatedAt }),
            dslVersion = dto.contractVersion,
            startIndex = start,
            scenes = scenes,
            degraded = dto.degraded.mapNotNull(::degradeLabel),
        )
    }

    private fun parseClassicScenePlan(scene: ClassroomPlaybackSceneDto, index: Int): NativeScenePlan? {
        val id = scene.id.ifBlank { "scene_$index" }
        val render = scene.render
        val kindRaw = render["kind"].asText().lowercase(Locale.ROOT)
        val sandbox = render["sandbox"].asText()
        val renderKind = when (kindRaw) {
            "native" -> NativeRenderKind.NATIVE
            "sandbox-html" -> if (sandbox.contains("allow-same-origin", ignoreCase = true)) {
                NativeRenderKind.UNSUPPORTED
            } else {
                NativeRenderKind.SANDBOX_HTML
            }
            "sandbox-url" -> if (sandbox.contains("allow-same-origin", ignoreCase = true)) {
                NativeRenderKind.UNSUPPORTED
            } else {
                NativeRenderKind.SANDBOX_URL
            }
            "unsupported" -> NativeRenderKind.UNSUPPORTED
            else -> NativeRenderKind.MISSING
        }
        return NativeScenePlan(
            id = id,
            type = scene.type.ifBlank { "unknown" },
            title = scene.title.ifBlank { "未命名场景" },
            order = scene.order,
            renderKind = renderKind,
            sandbox = sandbox,
            sandboxPayload = scene.content?.get("html").asText()
                .ifBlank { scene.content?.get("url").asText() },
            widgetType = render["widget_type"].asText().ifBlank { null },
            renderReason = render["reason"].asText().ifBlank { null },
            steps = scene.steps.mapIndexed { stepIndex, item ->
                NativePlaybackStep(
                    actionId = item["action_id"].asText().ifBlank { item["actionId"].asText() }
                        .ifBlank { "step_$stepIndex" },
                    type = item["type"].asText().ifBlank { "unknown" },
                    mode = item["mode"].asText().ifBlank { "sync" },
                )
            },
            droppedActions = scene.droppedActions.mapNotNull { item ->
                item["action_id"].asText().ifBlank { item["reason"].asText() }.takeIf { it.isNotBlank() }
            },
            whiteboards = scene.whiteboards,
            multiAgent = scene.multiAgent,
        )
    }

    private fun flattenPlaybackAction(action: Map<String, Any?>): Map<String, Any?> {
        val payload = action["payload"].asMap().orEmpty()
        return payload + action
    }

    private fun revisionOf(contentVersion: String): Int {
        if (contentVersion.isBlank()) return 0
        val hash = contentVersion.hashCode()
        return if (hash == Int.MIN_VALUE) Int.MAX_VALUE else kotlin.math.abs(hash)
    }

    fun parseDocument(
        document: Map<String, Any?>,
        stageId: String,
        fallbackTitle: String,
        revision: Int,
        dslVersion: String = "",
    ): NativeStageDocument {
        val stageMap = document["stage"].asMap().orEmpty()
        val title = stageMap["title"].asText().ifBlank { fallbackTitle }.ifBlank { "课堂" }
        val scenes = document["scenes"].asList().orEmpty()
            .mapIndexedNotNull { index, raw ->
                val map = raw.asMap() ?: return@mapIndexedNotNull null
                val id = map["id"].asText().ifBlank { "scene_$index" }
                val content = map["content"].asMap().orEmpty()
                val type = map["type"].asText().ifBlank { content["type"].asText() }.ifBlank { "slide" }
                NativeScene(
                    id = id,
                    stageId = map["stageId"].asText().ifBlank { stageId },
                    title = map["title"].asText().ifBlank { "第 ${index + 1} 页" },
                    type = type,
                    order = map["order"].asInt() ?: index,
                    content = content,
                    actions = map["actions"].asList().orEmpty().mapIndexedNotNull { actionIndex, item ->
                        item.asMap()?.let { parseAction(it, actionIndex) }
                    },
                    whiteboards = map["whiteboards"].asList().orEmpty()
                        .mapIndexedNotNull { boardIndex, item -> parseSlide(item.asMap(), "wb_${id}_$boardIndex") },
                    multiAgent = map["multiAgent"].asBoolean() ?: false,
                )
            }
            .sortedBy { it.order }

        val slides = linkedMapOf<String, NativeSlide>()
        val quizzes = linkedMapOf<String, NativeQuiz>()
        val pbls = linkedMapOf<String, NativePblProject>()
        val interactive = linkedMapOf<String, NativeInteractive>()
        scenes.forEach { scene ->
            when (scene.type) {
                "slide" -> parseSlide(scene.content["canvas"].asMap(), scene.id)?.let { slides[scene.id] = it }
                "quiz" -> parseQuiz(scene.content)?.let { quizzes[scene.id] = it }
                "pbl" -> parsePbl(scene.content, scene.title)?.let { pbls[scene.id] = it }
                "interactive" -> interactive[scene.id] = parseInteractive(scene.content)
            }
        }

        return NativeStageDocument(
            stageId = stageId,
            title = title,
            revision = revision,
            dslVersion = dslVersion,
            scenes = scenes,
            slideByScene = slides,
            quizByScene = quizzes,
            pblByScene = pbls,
            interactiveByScene = interactive,
            whiteboard = parseWhiteboard(stageMap["whiteboard"], scenes),
        )
    }

    private fun parseScenePlan(dto: MagicClassScenePlaybackDto): NativeScenePlan? {
        val id = dto.id.asText()
        if (id.isBlank()) return null
        val render = dto.render.asMap().orEmpty()
        val kindRaw = render["kind"].asText().lowercase(Locale.ROOT)
        val sandbox = render["sandbox"].asText()
        val allowsSameOrigin = sandbox.contains("allow-same-origin", ignoreCase = true)
        val renderKind = when (kindRaw) {
            "native" -> NativeRenderKind.NATIVE
            "sandbox-html" -> if (allowsSameOrigin) {
                NativeRenderKind.UNSUPPORTED
            } else {
                NativeRenderKind.SANDBOX_HTML
            }
            "sandbox-url" -> if (allowsSameOrigin) {
                NativeRenderKind.UNSUPPORTED
            } else {
                NativeRenderKind.SANDBOX_URL
            }
            "unsupported" -> NativeRenderKind.UNSUPPORTED
            else -> NativeRenderKind.MISSING
        }
        val reason = render["reason"].asText().ifBlank {
            if (renderKind == NativeRenderKind.UNSUPPORTED && kindRaw == "sandbox-html") {
                "sandbox_policy_rejects_same_origin"
            } else {
                ""
            }
        }.ifBlank { null }
        return NativeScenePlan(
            id = id,
            type = dto.type.ifBlank { "unknown" },
            title = dto.title.ifBlank { "未命名场景" },
            order = dto.order,
            renderKind = renderKind,
            sandbox = sandbox,
            widgetType = render["widget_type"].asText().ifBlank { null },
            renderReason = reason,
            steps = dto.steps.orEmpty().mapIndexedNotNull { index, item ->
                val map = item.asMap() ?: return@mapIndexedNotNull null
                NativePlaybackStep(
                    actionId = map["action_id"].asText().ifBlank { map["actionId"].asText() }.ifBlank { "step_$index" },
                    type = map["type"].asText().ifBlank { "unknown" },
                    mode = map["mode"].asText().ifBlank { "sync" },
                )
            },
            droppedActions = dto.droppedActions.orEmpty().mapNotNull { item ->
                val text = item.asText().ifBlank {
                    item.asMap()?.let { map ->
                        map["action_id"].asText().ifBlank { map["reason"].asText() }
                    }.orEmpty()
                }
                text.takeIf { it.isNotBlank() }
            },
            whiteboards = dto.whiteboards,
            multiAgent = dto.multiAgent,
        )
    }

    fun parseSlide(raw: Map<String, Any?>?, fallbackId: String = "slide"): NativeSlide? {
        if (raw == null) return null
        val theme = raw["theme"].asMap().orEmpty()
        val backgroundMap = raw["background"].asMap().orEmpty()
        val gradient = backgroundMap["gradient"].asMap().orEmpty()
        val gradientColors = gradient["colors"].asList().orEmpty()
            .mapNotNull { item -> item.asText().takeIf { it.isNotBlank() } }
        val background = NativeSlideBackground(
            color = backgroundMap["color"].asText().ifBlank { theme["backgroundColor"].asText() }.ifBlank { null },
            imageUrl = backgroundMap["image"].asMap()?.get("src").asText().ifBlank { null },
            gradientColors = gradientColors,
        )
        val elements = raw["elements"].asList().orEmpty().mapIndexedNotNull { index, item ->
            item.asMap()?.let { parseElement(it, index) }
        }
        return NativeSlide(
            id = raw["id"].asText().ifBlank { fallbackId },
            viewportSize = raw["viewportSize"].asDouble()?.takeIf { it > 0 } ?: 1000.0,
            viewportRatio = raw["viewportRatio"].asDouble()?.takeIf { it > 0 } ?: (9.0 / 16.0),
            theme = NativeSlideTheme(
                backgroundColor = theme["backgroundColor"].asText().ifBlank { null },
                fontColor = theme["fontColor"].asText().ifBlank { null },
                fontName = theme["fontName"].asText().ifBlank { null },
            ),
            background = background,
            elements = elements,
        )
    }

    private fun parseElement(map: Map<String, Any?>, index: Int): NativeCanvasElement {
        val id = map["id"].asText().ifBlank { "el_$index" }
        val left = map["left"].asDouble() ?: 0.0
        val top = map["top"].asDouble() ?: 0.0
        val width = map["width"].asDouble() ?: 0.0
        val height = map["height"].asDouble() ?: 0.0
        val rotate = map["rotate"].asDouble() ?: 0.0
        val opacity = (map["opacity"].asDouble() ?: 1.0).coerceIn(0.0, 1.0)
        val type = map["type"].asText().lowercase(Locale.ROOT)
        val common = Geometry(id, left, top, width, height, rotate, opacity)
        return when (type) {
            "text" -> {
                val html = map["content"].asText()
                val textType = map["textType"].asText().ifBlank { null }
                val fallbackSize = when (textType) {
                    "title" -> 44.0
                    "subtitle" -> 30.0
                    "notes" -> 12.0
                    else -> 18.0
                }
                val parsed = NativeClassroomText.parse(
                    html = html,
                    fallbackColor = map["defaultColor"].asText().ifBlank { null },
                    fallbackFontSize = fallbackSize,
                    fallbackBold = textType == "title",
                    fallbackAlign = map["textAlign"].asText().ifBlank { "left" },
                )
                NativeCanvasElement.Text(
                    id = common.id,
                    left = common.left,
                    top = common.top,
                    width = common.width,
                    height = common.height,
                    rotate = common.rotate,
                    opacity = common.opacity,
                    html = html,
                    plainText = parsed.plainText,
                    fontColor = parsed.color,
                    fontSize = parsed.fontSize,
                    bold = parsed.bold,
                    italic = parsed.italic,
                    underline = parsed.underline,
                    align = parsed.align,
                    verticalAlign = map["vAlign"].asText().ifBlank { "top" },
                    lineHeight = map["lineHeight"].asDouble()?.takeIf { it > 0 } ?: 1.5,
                    textType = textType,
                )
            }
            "shape" -> {
                val outline = map["outline"].asMap().orEmpty()
                NativeCanvasElement.Shape(
                    id = common.id,
                    left = common.left,
                    top = common.top,
                    width = common.width,
                    height = common.height,
                    rotate = common.rotate,
                    opacity = common.opacity,
                    shapeType = map["shapeType"].asText().ifBlank { "rect" },
                    fill = map["fill"].asText().ifBlank { null },
                    stroke = outline["color"].asText().ifBlank { null },
                    strokeWidth = outline["width"].asDouble() ?: 0.0,
                    radius = map["radius"].asDouble() ?: 0.0,
                )
            }
            "line" -> {
                val start = map["start"].asList().orEmpty()
                val end = map["end"].asList().orEmpty()
                NativeCanvasElement.Line(
                    id = common.id,
                    left = common.left,
                    top = common.top,
                    width = common.width,
                    height = common.height,
                    rotate = common.rotate,
                    opacity = common.opacity,
                    startX = start.getOrNull(0).asDouble() ?: 0.0,
                    startY = start.getOrNull(1).asDouble() ?: 0.0,
                    endX = end.getOrNull(0).asDouble() ?: common.width,
                    endY = end.getOrNull(1).asDouble() ?: common.height,
                    color = map["color"].asText().ifBlank { map["fill"].asText() }.ifBlank { null },
                    strokeWidth = map["strokeWidth"].asDouble() ?: map["lineWidth"].asDouble() ?: 1.0,
                )
            }
            "image" -> NativeCanvasElement.Image(
                id = common.id,
                left = common.left,
                top = common.top,
                width = common.width,
                height = common.height,
                rotate = common.rotate,
                opacity = common.opacity,
                source = map["src"].asAssetText(),
                radius = map["radius"].asDouble() ?: 0.0,
            )
            "video" -> NativeCanvasElement.Video(
                id = common.id,
                left = common.left,
                top = common.top,
                width = common.width,
                height = common.height,
                rotate = common.rotate,
                opacity = common.opacity,
                source = map["src"].asAssetText().ifBlank { map["mediaRef"].asAssetText() },
                poster = map["poster"].asText().ifBlank { null },
            )
            "table" -> {
                val rows = map["data"].asList().orEmpty().map { row ->
                    NativeTableCellRow(
                        row.asList().orEmpty().mapIndexed { cellIndex, cell ->
                            val cellMap = cell.asMap().orEmpty()
                            val style = cellMap["style"].asMap().orEmpty()
                            NativeTableCell(
                                text = NativeClassroomText.stripSimple(cellMap["text"].asText()),
                                colspan = (cellMap["colspan"].asInt() ?: 1).coerceAtLeast(1),
                                rowspan = (cellMap["rowspan"].asInt() ?: 1).coerceAtLeast(1),
                                bold = style["bold"].asBoolean() ?: false,
                                align = style["align"].asText().ifBlank { "left" },
                                fill = style["backgroundColor"].asText().ifBlank { null },
                                color = style["color"].asText().ifBlank { null },
                            )
                        }
                    )
                }
                val columns = rows.maxOfOrNull { it.cells.sumOf { cell -> cell.colspan } } ?: 0
                val weights = map["colWidths"].asList().orEmpty().mapNotNull { it.asDouble() }
                    .let { list ->
                        when {
                            list.isEmpty() -> List(columns.coerceAtLeast(1)) { 1.0 / columns.coerceAtLeast(1) }
                            list.size == columns -> list
                            else -> List(columns.coerceAtLeast(1)) { 1.0 / columns.coerceAtLeast(1) }
                        }
                    }
                val outline = map["outline"].asMap().orEmpty()
                val theme = map["theme"].asMap().orEmpty()
                NativeCanvasElement.Table(
                    id = common.id,
                    left = common.left,
                    top = common.top,
                    width = common.width,
                    height = common.height,
                    rotate = common.rotate,
                    opacity = common.opacity,
                    rows = rows,
                    columnWeights = weights,
                    rowHeights = map["rowHeights"].asList().orEmpty().mapNotNull { it.asDouble() },
                    borderColor = outline["color"].asText().ifBlank { "#D8D8D8" },
                    headerFill = theme["color"].asText().ifBlank { null },
                    textColor = theme["textColor"].asText().ifBlank { null },
                )
            }
            "chart" -> {
                val data = map["data"].asMap().orEmpty()
                val labels = data["labels"].asList().orEmpty().map { it.asText() }
                val rawSeries = data["series"].asList().orEmpty()
                val series = rawSeries.map { entry ->
                    entry.asList()?.mapNotNull { it.asDouble() }
                        ?: listOfNotNull(entry.asDouble())
                }
                NativeCanvasElement.Chart(
                    id = common.id,
                    left = common.left,
                    top = common.top,
                    width = common.width,
                    height = common.height,
                    rotate = common.rotate,
                    opacity = common.opacity,
                    chartType = map["chartType"].asText().ifBlank { "bar" },
                    labels = labels,
                    series = series,
                    colors = map["themeColors"].asList().orEmpty().map { it.asText() }.filter { it.isNotBlank() },
                    textColor = map["textColor"].asText().ifBlank { null },
                    lineColor = map["lineColor"].asText().ifBlank { null },
                )
            }
            "latex" -> NativeCanvasElement.Latex(
                id = common.id,
                left = common.left,
                top = common.top,
                width = common.width,
                height = common.height,
                rotate = common.rotate,
                opacity = common.opacity,
                latex = map["latex"].asText().ifBlank { map["content"].asText() },
                color = map["color"].asText().ifBlank { null },
                fontSize = map["fontSize"].asDouble(),
            )
            "audio" -> NativeCanvasElement.Audio(
                id = common.id,
                left = common.left,
                top = common.top,
                width = common.width,
                height = common.height,
                rotate = common.rotate,
                opacity = common.opacity,
                source = map["src"].asAssetText().ifBlank { map["mediaRef"].asAssetText() },
            )
            else -> NativeCanvasElement.Unknown(
                id = common.id,
                left = common.left,
                top = common.top,
                width = common.width,
                height = common.height,
                rotate = common.rotate,
                opacity = common.opacity,
                type = type.ifBlank { "unknown" },
            )
        }
    }

    private fun parseQuiz(content: Map<String, Any?>): NativeQuiz? {
        val items = content["questions"].asList().orEmpty()
        if (items.isEmpty()) return null
        val questions = items.mapIndexedNotNull { index, raw ->
            val map = raw.asMap() ?: return@mapIndexedNotNull null
            val id = map["id"].asText().ifBlank { "q${index + 1}" }
            val prompt = listOf("question", "prompt", "stem", "text")
                .map { NativeClassroomText.stripSimple(map[it].asText()) }
                .firstOrNull { it.isNotBlank() }
                .orEmpty()
            val options = map["options"].asList().orEmpty().mapIndexedNotNull { optionIndex, option ->
                val optionMap = option.asMap()
                if (optionMap != null) {
                    val value = listOf("value", "text", "content", "id")
                        .map { optionMap[it].asText().trim() }
                        .firstOrNull { it.isNotBlank() }
                        .orEmpty()
                    val label = listOf("label", "key", "id")
                        .map { NativeClassroomText.stripSimple(optionMap[it].asText()) }
                        .firstOrNull { it.isNotBlank() }
                        ?: quizOptionLabel(optionIndex)
                    if (value.isBlank()) null else NativeQuizOption(label = label, value = value)
                } else {
                    val text = NativeClassroomText.stripSimple(option.asText())
                    if (text.isBlank()) null else NativeQuizOption(label = quizOptionLabel(optionIndex), value = text)
                }
            }
            val answerKey = quizAnswerValues(
                map["answer"] ?: map["answerKey"] ?: map["correctAnswer"],
                options,
            )
            NativeQuestion(
                id = id,
                number = index + 1,
                type = map["type"].asText().ifBlank { "single" },
                question = prompt,
                options = options,
                answerKey = answerKey,
                analysis = listOf("analysis", "explanation", "solution")
                    .map { NativeClassroomText.stripSimple(map[it].asText()) }
                    .firstOrNull { it.isNotBlank() }
                    .orEmpty(),
                commentPrompt = map["commentPrompt"].asText(),
                hasAnswer = map["hasAnswer"].asBoolean() ?: answerKey.isNotEmpty(),
                points = map["points"].asDouble()?.takeIf { it > 0 } ?: 1.0,
            )
        }
        return NativeQuiz(questions)
    }

    private fun quizOptionLabel(index: Int): String =
        if (index in 0..25) ('A'.code + index).toChar().toString() else (index + 1).toString()

    /** 兼容对象选项、字符串选项以及数字索引答案。 */
    private fun quizAnswerValues(raw: Any?, options: List<NativeQuizOption>): List<String> {
        val entries = when (raw) {
            null -> emptyList()
            is List<*> -> raw
            is Array<*> -> raw.toList()
            else -> listOf(raw)
        }
        return entries.mapNotNull { entry ->
            when (entry) {
                is Number -> options.getOrNull(entry.toInt())?.value ?: entry.toString()
                else -> {
                    val text = entry.asText().trim()
                    if (text.isBlank()) {
                        null
                    } else {
                        options.firstOrNull { it.value == text || it.label == text }?.value ?: text
                    }
                }
            }
        }.filter { it.isNotBlank() }
    }

    private fun parsePbl(content: Map<String, Any?>, sceneTitle: String): NativePblProject? {
        val projectV2 = content["projectV2"].asMap()
        val legacyProject = content["project"].asMap()
        if (projectV2 != null || legacyProject != null) {
            val project = projectV2 ?: legacyProject!!
            val roles = project["roles"].asList().orEmpty().mapNotNull { it.asMap() }
            val instructor = roles.firstOrNull { it["type"].asText() == "instructor" }
            val milestones = (project["milestones"] ?: project["phases"]).asList().orEmpty()
                .mapIndexedNotNull { index, raw ->
                    val map = raw.asMap() ?: return@mapIndexedNotNull null
                    NativePblMilestone(
                        title = map["title"].asText().ifBlank { "阶段 ${index + 1}" },
                        description = map["description"].asText().ifBlank { map["briefing"].asText() },
                        status = map["status"].asText().ifBlank { if (index == 0) "active" else "todo" },
                        tasks = collectPblTasks(map),
                    )
                }
            return NativePblProject(
                title = project["title"].asText().ifBlank { sceneTitle },
                description = project["description"].asText(),
                instructorName = instructor?.get("name").asText()?.ifBlank { null },
                milestones = milestones,
            )
        }

        val phases = (content["phases"] ?: content).asList().orEmpty()
        if (phases.isEmpty() && content["title"].asText().isBlank()) return null
        val entries = if (phases.isNotEmpty()) phases else listOf(content)
        val milestones = entries.mapIndexedNotNull { index, raw ->
            val map = raw.asMap() ?: return@mapIndexedNotNull null
            NativePblMilestone(
                title = map["title"].asText().ifBlank { "阶段 ${index + 1}" },
                description = map["description"].asText(),
                status = map["status"].asText().ifBlank { if (index == 0) "active" else "todo" },
                tasks = collectPblTasks(map),
            )
        }
        return NativePblProject(
            title = content["title"].asText().ifBlank { sceneTitle },
            description = content["description"].asText(),
            instructorName = null,
            milestones = milestones,
        )
    }

    private fun collectPblTasks(map: Map<String, Any?>): List<NativePblTask> {
        val rawTasks = map["microtasks"] ?: map["tasks"]
        return rawTasks.asList().orEmpty().mapIndexedNotNull { index, raw ->
            when (raw) {
                is String -> if (raw.isBlank()) null else NativePblTask(
                    title = raw,
                    description = raw,
                    status = if (index == 0) "in_progress" else "todo",
                )
                else -> raw.asMap()?.let { task ->
                    NativePblTask(
                        title = task["title"].asText().ifBlank { "任务 ${index + 1}" },
                        description = task["description"].asText(),
                        status = task["status"].asText().ifBlank { "todo" },
                        hints = task["hints"].asList().orEmpty().map { it.asText() }.filter { it.isNotBlank() },
                    )
                }
            }
        }
    }

    private fun parseInteractive(content: Map<String, Any?>): NativeInteractive = NativeInteractive(
        html = content["html"].asText().ifBlank { content["markup"].asText() }.ifBlank { null },
        url = content["url"].asText().ifBlank { content["iframeUrl"].asText() }.ifBlank { null },
        widgetType = content["widgetType"].asText().ifBlank { content["widget"].asText() }.ifBlank { null },
        title = content["title"].asText().ifBlank { null },
        description = content["description"].asText().ifBlank { null },
        limitExperiment = if (content["widgetType"] == "simulation") {
            ClassroomLimitExperiment.fromWidgetConfig(content["widgetConfig"])
        } else null,
        spatialExperiment = if (content["widgetType"] == "visualization3d") {
            ClassroomSpatialExperiment.fromWidgetConfig(content["widgetConfig"])
        } else null,
        parameterExperiment = if (content["widgetType"] == "simulation") {
            ClassroomParameterExperiment.fromWidgetConfig(content["widgetConfig"])
        } else null,
    )

    private fun parseWhiteboard(raw: Any?, scenes: List<NativeScene>): NativeSlide? {
        val candidates = when (raw) {
            is List<*> -> raw
            null -> scenes.asSequence().mapNotNull { it.whiteboards.firstOrNull() }.toList()
            else -> listOf(raw)
        }
        for (candidate in candidates) {
            val map = candidate.asMap() ?: continue
            val slide = parseSlide(map, "whiteboard_1")
            if (slide != null && slide.elements.isNotEmpty()) return slide
        }
        return null
    }

    private fun parseAction(map: Map<String, Any?>, index: Int): NativeAction {
        val type = map["type"].asText().ifBlank { "unknown" }
        val content = map["content"].asMap().orEmpty()
        val duration = map["durationMs"].asDouble()
            ?: map["duration"].asDouble()?.let { if (it < 100) it * 1000 else it }
            ?: 0.0
        return NativeAction(
            id = map["id"].asText().ifBlank { "action_$index" },
            type = type,
            title = map["title"].asText().ifBlank { actionTitle(type) },
            description = NativeClassroomText.stripSimple(map["description"].asText()),
            elementId = map["elementId"].asText().ifBlank { map["element_id"].asText() }.ifBlank { null },
            color = map["color"].asText().ifBlank { null },
            dimOpacity = (map["dimOpacity"].asDouble() ?: 0.75).coerceIn(0.0, 1.0),
            durationMs = ((duration.takeIf { it > 0 } ?: 0.0)).toLong(),
            speech = map["text"].asText().ifBlank { map["speech"].asText() }
                .ifBlank { content["text"].asText() }.ifBlank { null },
            videoUrl = map["src"].asText().ifBlank { map["url"].asText() }
                .ifBlank { map["videoUrl"].asText() }.ifBlank { null },
            audioUrl = map["audioUrl"].asText().ifBlank { map["audio_url"].asText() }
                .ifBlank { content["audioUrl"].asText() }.ifBlank { null },
            supported = map["supported"].asBoolean() ?: true,
            reason = map["reason"].asText().ifBlank { null },
            widgetTarget = if (type == "widget_highlight") map["target"].asText().ifBlank { null } else null,
            widgetState = if (type == "widget_setState" || type == "widget_set_state") map["state"].asMap() else null,
        )
    }

    private fun actionTitle(type: String): String = when (type) {
        "spotlight" -> "聚焦"
        "laser" -> "激光指示"
        "play_video" -> "播放视频"
        "speech" -> "老师讲解"
        "wb_open" -> "打开白板"
        "wb_draw_text" -> "白板写字"
        "wb_draw_shape" -> "白板画图"
        "wb_draw_chart" -> "白板图表"
        "wb_draw_latex" -> "白板公式"
        "wb_draw_table" -> "白板表格"
        "wb_draw_line" -> "白板连线"
        "wb_clear" -> "清空白板"
        "wb_delete" -> "删除白板元素"
        "wb_close" -> "收起白板"
        "discussion" -> "课堂讨论"
        "widget_highlight" -> "高亮互动"
        "widget_setState", "widget_set_state" -> "调整参数"
        "widget_annotation" -> "互动批注"
        "widget_reveal" -> "揭示答案"
        else -> type
    }

    private fun degradeLabel(raw: Any?): String? {
        if (raw == null) return null
        val map = raw.asMap()
        val text = if (map != null) {
            map["reason"].asText().ifBlank { map["message"].asText() }.ifBlank { map["code"].asText() }
        } else {
            raw.asText()
        }
        return text.ifBlank { null }
    }

    private data class Geometry(
        val id: String,
        val left: Double,
        val top: Double,
        val width: Double,
        val height: Double,
        val rotate: Double,
        val opacity: Double,
    )
}

// 动态 JSON 的窄化工具。服务端文档是开放对象，所有字段都按"有就取，没有就降级"处理。

internal fun Any?.asMap(): Map<String, Any?>? {
    val source = this as? Map<*, *> ?: return null
    val result = LinkedHashMap<String, Any?>(source.size)
    source.forEach { (key, value) ->
        result[key?.toString().orEmpty()] = value
    }
    return result
}

internal fun Any?.asList(): List<Any?>? = this as? List<*>

internal fun Any?.asText(): String = when (this) {
    null -> ""
    is String -> this
    is Number -> {
        val value = toDouble()
        if (value % 1.0 == 0.0) value.toLong().toString() else value.toString()
    }
    is Boolean -> if (this) "true" else "false"
    else -> ""
}

internal fun Any?.asAssetText(): String = when (this) {
    is String -> this
    is Map<*, *> -> get("src").asText().ifBlank { get("url").asText() }.ifBlank { get("ref").asText() }
    else -> ""
}

internal fun Any?.asDouble(): Double? = when (this) {
    is Number -> toDouble()
    is String -> toDoubleOrNull()
    else -> null
}

internal fun Any?.asInt(): Int? = asDouble()?.toInt()

internal fun Any?.asBoolean(): Boolean? = when (this) {
    is Boolean -> this
    is String -> when (lowercase(Locale.ROOT)) {
        "true", "1", "yes" -> true
        "false", "0", "no" -> false
        else -> null
    }
    is Number -> toInt() != 0
    else -> null
}
