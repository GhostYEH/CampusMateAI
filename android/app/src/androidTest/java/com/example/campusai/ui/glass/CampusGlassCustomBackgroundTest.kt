package com.example.campusai.ui.glass

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.Text
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import org.junit.Rule
import org.junit.Test

class CampusGlassCustomBackgroundTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun customBackgroundAndForegroundAreBothComposed() {
        composeRule.setContent {
            CampusGlassScene(
                darkMode = true,
                background = { Box(Modifier.testTag("scene-background")) },
            ) {
                Text("foreground", Modifier.testTag("scene-foreground"))
            }
        }

        composeRule.onNodeWithTag("scene-background").assertIsDisplayed()
        composeRule.onNodeWithTag("scene-foreground").assertIsDisplayed()
    }
}
