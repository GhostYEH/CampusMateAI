package com.example.campusai.ui.screens.focus

import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.campusai.data.focus.scene.FocusScene
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class FocusSceneContinuityTest {
    @get:Rule
    val composeRule = createComposeRule()

    @Test
    fun changingSceneDoesNotDisposeRobotContent() {
        val scene = mutableStateOf(FocusScene.RAINY_ROOM)
        var robotDisposals = 0

        composeRule.setContent {
            FocusSceneStage(
                scene = scene.value,
                robotContent = {
                    DisposableEffect(Unit) {
                        onDispose { robotDisposals++ }
                    }
                },
            )
        }

        composeRule.runOnIdle { scene.value = FocusScene.QUIET_LIBRARY }
        composeRule.waitForIdle()

        assertEquals(0, robotDisposals)
    }
}
