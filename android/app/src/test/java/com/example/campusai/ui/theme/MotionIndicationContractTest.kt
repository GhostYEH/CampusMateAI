package com.example.campusai.ui.theme

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MotionIndicationContractTest {
    @Test
    fun customPressIndicationUsesModifierNodeApi() {
        val source = productionSource("com/example/campusai/ui/theme/Motion.kt")

        assertTrue(source.contains("IndicationNodeFactory"))
        assertTrue(source.contains("DrawModifierNode"))
        assertFalse(source.contains("IndicationInstance"))
        assertFalse(source.contains("rememberUpdatedInstance"))
    }

    private fun productionSource(relativePath: String): String {
        val candidates = listOf(
            File("src/main/java", relativePath),
            File("app/src/main/java", relativePath),
        )
        return requireNotNull(candidates.firstOrNull(File::isFile)) {
            "Unable to locate production source: $relativePath"
        }.readText()
    }
}
