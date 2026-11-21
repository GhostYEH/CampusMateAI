package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.ui.screens.courses.nativeplayer.classroomSlideTemplate
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertSame
import org.junit.Test

class NativeSlideTemplateTest {
    private val stockCanvas = requireNotNull(
        NativeClassroomParser.parseSlide(mapOf(
            "theme" to mapOf("backgroundColor" to "#ffffff", "fontColor" to "#1f2937"),
            "elements" to listOf(
                mapOf("id" to "el_title", "type" to "text", "left" to 46, "width" to 840,
                    "content" to """<p style="color:#1f2937">单调性</p>"""),
                mapOf("id" to "el_accent", "type" to "shape", "fill" to "#722ed1"),
                mapOf("id" to "el_card_1", "type" to "shape", "fill" to "#f5f3ff"),
                mapOf("id" to "diagram", "type" to "image", "src" to "media/graph.png"),
            ),
        )),
    )

    @Test
    fun `classroom palette preserves the lesson and its canvas geometry`() {
        val presentation = classroomSlideTemplate(stockCanvas)
        val originalTitle = stockCanvas.elements.first() as NativeCanvasElement.Text
        val title = presentation.elements.first() as NativeCanvasElement.Text
        assertEquals(stockCanvas.aspectRatio, presentation.aspectRatio)
        assertEquals(stockCanvas.elements.map { it.id }, presentation.elements.map { it.id })
        assertEquals(originalTitle.copy(fontColor = title.fontColor), title)
        assertNotEquals(originalTitle.fontColor, title.fontColor)
        assertEquals(2, presentation.background.gradientColors.size)
        assertSame(stockCanvas.elements.last(), presentation.elements.last())
    }

    @Test
    fun `a custom background or missing template marks preserves the authored design`() {
        val illustrated = stockCanvas.copy(background = stockCanvas.background.copy(imageUrl = "media/paper.png"))
        val custom = stockCanvas.copy(elements = stockCanvas.elements.filterNot { it.id == "el_accent" })
        assertSame(illustrated, classroomSlideTemplate(illustrated))
        assertSame(custom, classroomSlideTemplate(custom))
    }
}
