package com.example.campusai.ui.glass

import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Test

class GlassControlCoverageTest {
    @Test
    fun `every Material control call is routed through the glass aliases`() {
        val sourceRoot = File("src/main/java")
        val controlNames = listOf(
            "Button",
            "OutlinedButton",
            "TextButton",
            "IconButton",
            "FloatingActionButton",
            "ExtendedFloatingActionButton",
            "Card",
        )
        val violations = sourceRoot.walkTopDown()
            .filter { it.isFile && it.extension == "kt" && it.name != "CampusGlassButtons.kt" }
            .flatMap { file ->
                val source = file.readText()
                controlNames.asSequence().mapNotNull { control ->
                    val usesControl = Regex("\\b$control\\s*\\(").containsMatchIn(source)
                    val usesGlassAlias = source.contains(
                        "import com.example.campusai.ui.components.Glass$control as $control",
                    )
                    if (usesControl && !usesGlassAlias) "${file.relativeTo(sourceRoot)}: $control" else null
                }
            }
            .toList()

        assertTrue(
            "Raw Material controls bypass liquid glass:\n${violations.joinToString("\n")}",
            violations.isEmpty(),
        )
    }
}
