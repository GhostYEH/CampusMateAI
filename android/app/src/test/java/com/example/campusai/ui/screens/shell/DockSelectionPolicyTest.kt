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
