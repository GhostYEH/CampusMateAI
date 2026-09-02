package com.example.campusai.ui.screens.focus

import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FocusExecutionModeContractTest {
    @Test
    fun displayModeDefaultsToImmersiveAndTogglesBack() {
        assertEquals(FocusExecutionDisplayMode.IMMERSIVE, FocusExecutionDisplayMode.DEFAULT)
        assertEquals(
            FocusExecutionDisplayMode.STANDARD,
            FocusExecutionDisplayMode.toggled(FocusExecutionDisplayMode.DEFAULT),
        )
        assertEquals(
            FocusExecutionDisplayMode.IMMERSIVE,
            FocusExecutionDisplayMode.toggled(FocusExecutionDisplayMode.STANDARD),
        )
    }

    @Test
    fun focusSessionDefaultsToImmersiveAndExposesStandardModeSwitch() {
        val source = Files.readAllBytes(focusAssistantSource()).toString(Charsets.UTF_8)

        assertTrue(source.contains("FocusExecutionDisplayMode.DEFAULT"))
        assertTrue(source.contains("FocusSceneStage("))
        assertTrue(source.contains("FocusSceneToolbar("))
        assertTrue(source.contains("专注空间"))
        assertTrue(source.contains("普通模式"))
    }

    private fun focusAssistantSource(): Path = sequenceOf(
        Paths.get("src/main/java/com/example/campusai/ui/screens/focus/FocusAssistantScreen.kt"),
        Paths.get("android/app/src/main/java/com/example/campusai/ui/screens/focus/FocusAssistantScreen.kt"),
    ).first(Files::exists)
}
