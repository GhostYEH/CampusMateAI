package com.example.campusai.data.local

/**
 * 首页展示样式偏好。
 *
 * 首页不再提供游戏化形态，只保留经典工作台与沉浸式校园首页两种非游戏化布局。
 * 历史上保存过 `gamified` 的设备会由 [fromStoredValue] 回落到 [CLASSIC]。
 */
enum class DashboardStyle(val storedValue: String) {
    CLASSIC("classic"),
    IMMERSIVE("immersive");

    companion object {
        fun fromStoredValue(value: String?): DashboardStyle =
            entries.firstOrNull { it.storedValue.equals(value?.trim(), ignoreCase = true) } ?: CLASSIC
    }
}
