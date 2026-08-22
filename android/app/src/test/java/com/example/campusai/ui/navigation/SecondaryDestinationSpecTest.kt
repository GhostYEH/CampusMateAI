package com.example.campusai.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test
import androidx.compose.ui.unit.dp

class SecondaryDestinationSpecTest {
    @Test
    fun secondaryRouteReceivesTitle() {
        assertEquals("系统设置", secondaryDestinationSpec("settings")?.title)
    }

    @Test
    fun notificationsRouteUsesItsActualFeatureName() {
        assertEquals("通知与提醒", secondaryDestinationSpec("notifications")?.title)
    }

    @Test
    fun rootRouteOmitsSecondaryChrome() {
        assertNull(secondaryDestinationSpec("home"))
    }

    @Test
    fun secondaryDestinationKeepsNavHostAtTopAndPadsOnlyItsOwnContent() {
        val layout = navigationDestinationLayout("settings", statusBarHeight = 24.dp)

        assertEquals(0.dp, layout.navHostTopPadding)
        assertEquals(84.dp, layout.contentTopPadding)
    }

    @Test
    fun rootPagesWithoutLocalStatusInsetReserveTheStatusBarInNavHostContent() {
        assertEquals(24.dp, navigationDestinationLayout("courses", 24.dp).contentTopPadding)
        assertEquals(24.dp, navigationDestinationLayout("tasks", 24.dp).contentTopPadding)
        assertEquals(24.dp, navigationDestinationLayout("counselor", 24.dp).contentTopPadding)
        assertEquals(0.dp, navigationDestinationLayout("home", 24.dp).contentTopPadding)
    }

    @Test
    fun lostFoundOwnsItsImmersiveHeroNavigation() {
        assertNull(secondaryDestinationSpec("lostfound"))
    }

    @Test
    fun argumentRouteResolvesTitle() {
        assertEquals("通知详情", secondaryDestinationSpec("campus-news-detail/news-42")?.title)
    }

    @Test
    fun allSecondaryRouteFamiliesResolveTitle() {
        listOf(
            "notifications",
            "task_calendar",
            "settings",
            "notification-settings",
            "chaoxing",
            "chaoxing-login",
            "expression-contribution",
            "account",
            "files",
            "activities",
            "favorites",
            "university",
            "community",
            "community_hot",
            "community_publish",
            "academic",
            "campus-news-detail/{newsId}",
            "task_detail/{taskId}",
            "exams",
            "exam_detail/{examId}",
            "exam_edit/{examId}",
            "classrooms",
            "focus",
            "lostfound_publish",
            "lostfound_detail/{itemId}",
            "lostfound_mine",
        ).forEach { route ->
            assertFalse("Route $route needs a fixed navigation title", secondaryDestinationSpec(route)?.title.isNullOrBlank())
        }
    }

    @Test
    fun communityHotRouteHasRankingTitle() {
        assertEquals("热门话题", secondaryDestinationSpec("community_hot")?.title)
    }
}
