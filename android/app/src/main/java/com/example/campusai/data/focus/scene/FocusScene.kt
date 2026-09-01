package com.example.campusai.data.focus.scene

enum class FocusScene(
    val storedId: String,
    val title: String,
    val subtitle: String,
) {
    RAINY_ROOM(
        storedId = "rainy_room",
        title = "雨夜自习室",
        subtitle = "让雨声替你隔开喧闹",
    ),
    QUIET_LIBRARY(
        storedId = "quiet_library",
        title = "静谧图书馆",
        subtitle = "在翻页声里稳稳向前",
    ),
    FOREST_MORNING(
        storedId = "forest_morning",
        title = "林间晨读",
        subtitle = "跟着清晨的风慢慢进入状态",
    );

    companion object {
        fun fromStoredId(value: String?): FocusScene =
            entries.firstOrNull { it.storedId == value } ?: RAINY_ROOM
    }
}

data class FocusSceneSettings(
    val scene: FocusScene,
    val ambientEnabled: Boolean,
    val volume: Float,
) {
    companion object {
        val DEFAULT = FocusSceneSettings(
            scene = FocusScene.RAINY_ROOM,
            ambientEnabled = false,
            volume = 0.32f,
        )

        fun normalized(
            sceneId: String?,
            ambientEnabled: Boolean,
            volume: Float,
        ): FocusSceneSettings = FocusSceneSettings(
            scene = FocusScene.fromStoredId(sceneId),
            ambientEnabled = ambientEnabled,
            volume = volume.takeIf(Float::isFinite)?.coerceIn(0f, 1f) ?: DEFAULT.volume,
        )
    }
}
