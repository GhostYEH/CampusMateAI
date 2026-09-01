package com.example.campusai.data.focus.scene

import android.content.Context

class FocusScenePreferenceStore(context: Context) {
    private val preferences = context.applicationContext.getSharedPreferences(
        PREFERENCES_NAME,
        Context.MODE_PRIVATE,
    )

    fun load(): FocusSceneSettings = FocusSceneSettings.normalized(
        sceneId = preferences.getString(KEY_SCENE, null),
        ambientEnabled = preferences.getBoolean(KEY_AMBIENT_ENABLED, false),
        volume = preferences.getFloat(KEY_VOLUME, FocusSceneSettings.DEFAULT.volume),
    )

    fun save(settings: FocusSceneSettings) {
        preferences.edit()
            .putString(KEY_SCENE, settings.scene.storedId)
            .putBoolean(KEY_AMBIENT_ENABLED, settings.ambientEnabled)
            .putFloat(KEY_VOLUME, settings.volume.coerceIn(0f, 1f))
            .apply()
    }

    private companion object {
        const val PREFERENCES_NAME = "focus_scene_preferences"
        const val KEY_SCENE = "scene"
        const val KEY_AMBIENT_ENABLED = "ambient_enabled"
        const val KEY_VOLUME = "ambient_volume"
    }
}
