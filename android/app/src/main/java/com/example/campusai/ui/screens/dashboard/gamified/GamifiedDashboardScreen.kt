package com.example.campusai.ui.screens.dashboard.gamified

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.campusai.ui.screens.shell.floatingDockContentBottomPadding
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.CampusAITheme

@Composable
fun GamifiedDashboardScreen(
    state: GamifiedDashboardUiState,
    onNavigate: (String) -> Unit,
) {
    var selectedAchievement by remember { mutableStateOf<AchievementUiState?>(null) }
    val listState = rememberLazyListState()
    BoxWithConstraints(Modifier.fillMaxSize().background(Background)) {
        val policy = remember(maxWidth) { DashboardLayoutPolicy.forWidthDp(maxWidth.value.toInt()) }
        val bottomPadding = floatingDockContentBottomPadding(
            WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
        )
        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().statusBarsPadding(),
            contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = bottomPadding),
            verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(14.dp),
        ) {
            item(key = "player-header") {
                PlayerHeader(state.player, state.reduceMotion) { onNavigate("profile") }
            }
            item(key = "daily-adventure") {
                DailyAdventureHero(state.adventure, state.reduceMotion, onNavigate)
            }
            if (state.isLoading || state.messages.isNotEmpty()) {
                item(key = "dashboard-status") { DashboardStatus(state.messages, state.isLoading) }
            }
            item(key = "main-quests") {
                MainQuestSection(state.mainQuests, state.mainQuestEmptyMessage, state.reduceMotion, onNavigate)
            }
            item(key = "side-quests") {
                SideQuestSection(state.sideQuests, policy.sideQuestColumns, onNavigate)
            }
            item(key = "growth") {
                GrowthSection(state.growth, policy.growthColumns)
            }
            item(key = "achievements") {
                AchievementSection(state.achievements, state.reduceMotion) { selectedAchievement = it }
            }
            item(key = "campus-world") {
                CampusWorldSection(state.campusWorld, onNavigate)
            }
        }
    }
    selectedAchievement?.let { AchievementDialog(it) { selectedAchievement = null } }
}

@Preview(name = "Small phone", widthDp = 320, heightDp = 720, showBackground = true)
@Composable
private fun GamifiedSmallPreview() {
    CampusAITheme { GamifiedDashboardScreen(previewState(), onNavigate = {}) }
}

@Preview(name = "Normal phone", widthDp = 390, heightDp = 844, showBackground = true)
@Composable
private fun GamifiedNormalPreview() {
    CampusAITheme { GamifiedDashboardScreen(previewState(), onNavigate = {}) }
}

@Preview(name = "Large phone", widthDp = 600, heightDp = 960, showBackground = true)
@Composable
private fun GamifiedLargePreview() {
    CampusAITheme { GamifiedDashboardScreen(previewState(), onNavigate = {}) }
}

private fun previewState() = GamifiedDashboardUiState(
    player = PlayerUiState("林知夏", 12, "成长先锋", 1240, 140, 375, .37f, 7),
    adventure = DailyAdventureUiState("期末挑战", "数据结构与算法设计实践 · 距离考试 3 天", 1, 2, .5f, 30, "exams"),
    mainQuests = listOf(
        MainQuestUiState("exam-1", "FINAL CHALLENGE", "数据结构与算法设计实践（荣誉课程）", "9月4日 · 09:00", "博学楼 1-401", "期末考试", 0, "exams", true),
        MainQuestUiState("task-1", "NEXT QUEST", "算法作业与复杂度分析报告终稿", "今天 23:59", "数据结构", "高优先级", 30, "tasks", false),
    ),
    mainQuestEmptyMessage = null,
    sideQuests = listOf(
        SideQuestUiState("专注自习", "开启一段真实专注", "focus"),
        SideQuestUiState("AI 导员", "规划下一步行动", "counselor"),
        SideQuestUiState("考试安排", "查看下一场挑战", "exams"),
    ),
    growth = GrowthUiState(320, 260, 18, 7),
    achievements = listOf(
        AchievementUiState("first-focus", "初心者", "完成第一次专注", true, "8月31日", 1, 1, "次专注"),
        AchievementUiState("focus-60", "专注起航", "累计专注 60 分钟", false, "", 42, 60, "分钟"),
    ),
    campusWorld = listOf(CampusWorldUiState("n1", "图书馆延长开放时间", "考试周开放至 22:00", "校园", "campus-news-detail/n1")),
    isLoading = false,
)
