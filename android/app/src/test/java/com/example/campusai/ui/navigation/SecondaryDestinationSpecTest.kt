package com.example.campusai.ui.navigation

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Test

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
    fun lostFoundUsesSharedSecondaryNavigation() {
        assertEquals("失物招领", secondaryDestinationSpec("lostfound")?.title)
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
            "campus-news-detail/{newsId}",
            "task_detail/{taskId}",
            "exams",
            "exam_detail/{examId}",
            "exam_edit/{examId}",
            "classrooms",
            "services",
            "service_leave",
            "service_repair",
            "service_form/{kind}",
            "service_mine",
            "service_detail/{requestId}",
            "focus",
            "lostfound_publish",
            "lostfound_detail/{itemId}",
            "lostfound_mine",
        ).forEach { route ->
            assertFalse("Route $route needs a fixed navigation title", secondaryDestinationSpec(route)?.title.isNullOrBlank())
        }
    }
}
