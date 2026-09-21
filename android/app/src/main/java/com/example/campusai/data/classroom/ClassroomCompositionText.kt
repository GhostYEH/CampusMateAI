package com.example.campusai.data.classroom

import com.example.campusai.data.remote.InteractiveClassroomCompositionDto

/**
 * 真实课堂组成的可读化。
 *
 * magic class 的真实 `scene.type` 只有 4 种：slide / quiz / interactive / pbl；
 * 3D、思维导图、编程、模拟、游戏都是 `interactive` 内部的 `widgetType`。
 *
 * 因此"这节课包含什么"**只能**来自回读结果，绝不能根据请求的 mode 推断 ——
 * 请求"思维导图"而实际只产出幻灯片时，展示的必须是幻灯片。
 */
object ClassroomCompositionText {

    private val SCENE_LABELS = mapOf(
        "slide" to "幻灯片",
        "quiz" to "测验",
        "interactive" to "互动实验",
        "pbl" to "项目式学习",
    )

    private val WIDGET_LABELS = mapOf(
        "simulation" to "流程/实验模拟",
        "diagram" to "结构图与思维导图",
        "code" to "在线编程",
        "game" to "知识小游戏",
        "visualization3d" to "3D 可视化",
        "procedural-skill" to "操作技能训练",
    )

    data class Part(val raw: String, val label: String, val count: Int, val known: Boolean)

    data class Description(
        val parts: List<Part>,
        val widgets: List<Part>,
        val extras: List<String>,
        val total: Int,
        val requires3d: Boolean,
        val external3dAvailable: Boolean,
        val degraded: Boolean,
        val error: String?,
    )

    fun describe(dto: InteractiveClassroomCompositionDto?): Description? {
        if (dto == null) return null
        val error = dto.error?.takeIf { it.isNotBlank() }
        if (error != null) {
            return Description(
                parts = emptyList(),
                widgets = emptyList(),
                extras = emptyList(),
                total = 0,
                requires3d = false,
                external3dAvailable = dto.external3dAvailable,
                degraded = false,
                error = error,
            )
        }
        val parts = dto.scenes.map { row ->
            Part(
                raw = row.type,
                label = SCENE_LABELS[row.type] ?: "未知类型（${row.type}）",
                count = row.count,
                known = SCENE_LABELS.containsKey(row.type),
            )
        }
        val widgets = dto.widgetTypes.map { row ->
            Part(
                raw = row.widgetType,
                label = WIDGET_LABELS[row.widgetType] ?: "未知形式（${row.widgetType}）",
                count = row.count,
                known = WIDGET_LABELS.containsKey(row.widgetType),
            )
        }
        val extras = buildList {
            if (dto.hasWhiteboard) add("白板推导")
            if (dto.hasTts) add("语音讲解")
            if (dto.hasMultiAgent) add("多智能体讨论")
        }
        return Description(
            parts = parts,
            widgets = widgets,
            extras = extras,
            total = dto.sceneTotal,
            requires3d = dto.requiresExternal3d,
            external3dAvailable = dto.external3dAvailable,
            degraded = dto.degraded,
            error = null,
        )
    }

    /** 例如："已生成内容包含：幻灯片 ×3、测验 ×1，另含 语音讲解"。 */
    fun summary(description: Description?): String {
        if (description == null) return ""
        description.error?.let { return "课堂内容读取失败：$it" }
        val pieces = description.parts.filter { it.count > 0 }.map { "${it.label} ×${it.count}" }
        val extras = if (description.extras.isEmpty()) "" else "，另含 ${description.extras.joinToString("、")}"
        if (pieces.isEmpty() && extras.isEmpty()) return "这节课没有生成可展示的内容"
        return "已生成内容包含：" + pieces.joinToString("、") + extras
    }

    /** 3D 依赖外部 CDN；不可达时是**降级**，不是整节课失败。 */
    fun threeDNotice(description: Description?): String? {
        val d = description ?: return null
        if (!d.requires3d) return null
        return if (d.external3dAvailable) {
            "这节课包含 3D 内容，需要能访问外部 CDN 才能正常查看。"
        } else {
            "这节课包含 3D 内容，但当前环境无法访问外部 3D 资源，这部分可能打不开。"
        }
    }
}
