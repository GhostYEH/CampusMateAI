package com.example.campusai.ui.screens.shell

import org.junit.Assert.assertEquals
import org.junit.Test

class DockSelectionPolicyTest {
    @Test
    fun lostFoundKeepsAiCampusAssistantSelected() {
        assertEquals("counselor", selectedStudentDockRoute("lostfound"))
    }

    @Test
    fun profileFlowKeepsProfileSelected() {
        assertEquals("profile", selectedStudentDockRoute("settings"))
        assertEquals("profile", selectedStudentDockRoute("university"))
        assertEquals("profile", selectedStudentDockRoute("academic"))
        assertEquals("profile", selectedStudentDockRoute("edu_system"))
        assertEquals("profile", selectedStudentDockRoute("edu_schedule"))
        assertEquals("profile", selectedStudentDockRoute("edu_login"))
    }

    @Test
    fun communityKeepsHomeSelected() {
        assertEquals("home", selectedStudentDockRoute("community"))
    }

    @Test
    fun primaryRouteSelectsItself() {
        assertEquals("courses", selectedStudentDockRoute("courses"))
    }
}
