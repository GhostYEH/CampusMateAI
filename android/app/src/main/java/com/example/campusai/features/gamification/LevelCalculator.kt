package com.example.campusai.features.gamification

object LevelCalculator {
    fun calculate(value: Int): LevelProgress {
        val totalXp = value.coerceAtLeast(0)
        var level = 1
        var currentXp = totalXp
        var nextLevelXp = 100

        while (currentXp >= nextLevelXp) {
            currentXp -= nextLevelXp
            level += 1
            nextLevelXp = 100 + 25 * (level - 1)
        }

        return LevelProgress(
            currentLevel = level,
            totalXp = totalXp,
            currentXp = currentXp,
            nextLevelXp = nextLevelXp,
            progress = currentXp.toFloat() / nextLevelXp,
        )
    }

    fun titleFor(level: Int): String = when {
        level >= 20 -> "校园领航者"
        level >= 10 -> "成长先锋"
        level >= 5 -> "校园探索者"
        else -> "校园新旅人"
    }
}
