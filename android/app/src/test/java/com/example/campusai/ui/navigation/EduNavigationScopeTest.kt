package com.example.campusai.ui.navigation

import androidx.navigation.NavBackStackEntry
import androidx.navigation.NavHostController
import org.junit.Assert.assertSame
import org.junit.Test
import org.mockito.Mockito.mock
import org.mockito.Mockito.`when`

class EduNavigationScopeTest {
    @Test
    fun webLoginUsesEduSystemBackStackEntryAsViewModelOwner() {
        val navController = mock(NavHostController::class.java)
        val eduSystemEntry = mock(NavBackStackEntry::class.java)
        `when`(navController.getBackStackEntry("edu_system")).thenReturn(eduSystemEntry)

        val owner = eduFlowViewModelOwner(navController)

        assertSame(eduSystemEntry, owner)
    }
}
