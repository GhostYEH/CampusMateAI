package com.example.campusai.ui.screens.dashboard.gamified

enum class SizeClass { COMPACT, NORMAL, WIDE }

data class DashboardLayoutPolicy(
    val sizeClass: SizeClass,
    val sideQuestColumns: Int,
    val growthColumns: Int,
) {
    companion object {
        fun forWidthDp(widthDp: Int): DashboardLayoutPolicy = when {
            widthDp < 360 -> DashboardLayoutPolicy(SizeClass.COMPACT, 2, 2)
            widthDp < 520 -> DashboardLayoutPolicy(SizeClass.NORMAL, 2, 4)
            else -> DashboardLayoutPolicy(SizeClass.WIDE, 3, 4)
        }
    }
}
