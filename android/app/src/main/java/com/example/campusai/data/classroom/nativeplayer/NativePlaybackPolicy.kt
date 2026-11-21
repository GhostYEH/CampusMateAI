package com.example.campusai.data.classroom.nativeplayer

enum class NativeSceneMode {
    NATIVE,
    SANDBOX_HTML,
    SANDBOX_URL,
    WEB_FALLBACK,
    UNAVAILABLE,
}

data class NativeSceneDisposition(
    val mode: NativeSceneMode,
    val reason: String? = null,
)

/**
 * 原生能力由「授权数据 + 服务端 render.kind + 场景能力」共同决定，
 * 不由页面类型或客户端猜测决定。不可原生渲染时，只有存在可信网页 URL 才回退。
 */
object NativePlaybackPolicy {
    fun decide(
        renderKind: NativeRenderKind,
        sceneType: String,
        hasDocument: Boolean,
        hasRenderableContent: Boolean,
        fallbackAvailable: Boolean,
        renderReason: String? = null,
        hasNativeExperiment: Boolean = false,
        hasNativeSpatialScene: Boolean = false,
    ): NativeSceneDisposition {
        if (sceneType == "interactive" && hasDocument) {
            val localAllowed = renderKind == NativeRenderKind.NATIVE || renderKind == NativeRenderKind.SANDBOX_HTML
            val externalCdnMissing = renderKind == NativeRenderKind.UNSUPPORTED && renderReason == "widget_requires_external_cdn"
            if ((localAllowed && (hasNativeExperiment || hasNativeSpatialScene)) || (hasNativeSpatialScene && externalCdnMissing)) {
                return NativeSceneDisposition(NativeSceneMode.NATIVE)
            }
        }
        return when (renderKind) {
            NativeRenderKind.NATIVE -> when {
                !hasDocument -> NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "missing_scene_content")
                !hasRenderableContent -> NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "scene_content_empty")
                sceneType == "interactive" -> NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "interactive_native_renderer_missing")
                sceneType !in setOf("slide", "quiz", "pbl", "interactive") ->
                    NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "scene_type_unsupported")
                else -> NativeSceneDisposition(NativeSceneMode.NATIVE)
            }
            NativeRenderKind.SANDBOX_HTML -> if (hasRenderableContent) {
                NativeSceneDisposition(NativeSceneMode.SANDBOX_HTML)
            } else if (fallbackAvailable) {
                NativeSceneDisposition(NativeSceneMode.WEB_FALLBACK, "interactive_payload_missing")
            } else {
                NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "interactive_payload_missing")
            }
            NativeRenderKind.SANDBOX_URL -> if (hasRenderableContent) {
                NativeSceneDisposition(NativeSceneMode.SANDBOX_URL)
            } else if (fallbackAvailable) {
                NativeSceneDisposition(NativeSceneMode.WEB_FALLBACK, "interactive_payload_missing")
            } else {
                NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, "sandbox_url_requires_trusted_runtime")
            }
            NativeRenderKind.UNSUPPORTED, NativeRenderKind.MISSING -> if (fallbackAvailable) {
                NativeSceneDisposition(NativeSceneMode.WEB_FALLBACK, renderReason ?: "render_unsupported")
            } else {
                NativeSceneDisposition(NativeSceneMode.UNAVAILABLE, renderReason ?: "render_unsupported")
            }
        }
    }

    fun reasonText(reason: String?): String = when (reason) {
        "missing_scene_content" -> "这份舞台没有下发这一页的正文，不能原生播放。"
        "scene_content_empty" -> "这一页没有可播放的正文内容。"
        "interactive_native_renderer_missing" -> "这个互动场景需要专用原生渲染器，当前版本尚未接入。"
        "scene_type_unsupported" -> "这个场景类型当前没有对应的渲染器。"
        "interactive_payload_missing" -> "该互动场景没有可播放的内容。"
        "sandbox_url_requires_trusted_runtime" -> "该互动需要受限网页运行时，但当前入口没有可信课堂地址。"
        "widget_requires_external_cdn" -> "该互动内容需要外部 3D/CDN 能力，本部署未启用。"
        "widget_type_unknown" -> "这个互动组件类型无法识别。"
        "render_unsupported" -> "这个场景当前无法原生播放。"
        else -> reason?.takeIf { it.isNotBlank() }?.let { "这个场景当前无法播放（$it）。" }
            ?: "这个场景当前无法播放。"
    }
}
