package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class NativeClassroomTextTest {

    @Test
    fun `html keeps line breaks list markers and inline style`() {
        val parsed = NativeClassroomText.parse(
            "<h1 style=\"font-size:32px;color:#285B4B;text-align:center\">标题</h1>" +
                "<p>第一行<br>第二行</p><ul><li>要点一</li><li>要点二</li></ul>",
        )
        assertTrue(parsed.plainText.contains("第一行\n第二行"))
        assertTrue(parsed.plainText.contains("• 要点一"))
        assertEquals(32.0, parsed.fontSize)
        assertEquals("#285B4B", parsed.color)
        assertEquals("center", parsed.align)
    }

    @Test
    fun `formula degrades to readable text`() {
        val text = NativeClassroomText.readableFormula("\\frac{a+b}{c} \\times \\sqrt{x^2}")
        assertTrue(text.contains("(a+b)/(c)"))
        assertTrue(text.contains("×"))
        assertTrue(text.contains("√(x²)"))
    }

    @Test
    fun `unknown tags never drop body text`() {
        val parsed = NativeClassroomText.parse("<custom>正文</custom><br>下一段")
        assertEquals("正文\n下一段", parsed.plainText)
    }

    @Test
    fun `plain and html explanations preserve inequalities`() {
        val comparison = "在 [0,2] 上任取 x₁<x₂，因 x₁≥0、x₂>x₁，故 x₂−x₁>0。"
        assertEquals(comparison, NativeClassroomText.stripSimple(comparison))
        assertEquals(
            "$comparison\na<b and b>a",
            NativeClassroomText.parse("<p>$comparison</p><p>a<b and b>a</p>").plainText,
        )
    }

    @Test
    fun `lecture follows the generated PPT sections and speaks math operators`() {
        val slide = requireNotNull(NativeClassroomParser.parseSlide(mapOf(
            "elements" to listOf(
                mapOf("type" to "text", "content" to "<p>推导步骤</p>"),
                mapOf("type" to "text", "content" to "<ul><li>任取 x₁&lt;x₂</li><li>f(x)=x²</li></ul>"),
                mapOf("type" to "text", "content" to "<p>隐藏文字</p>", "opacity" to 0),
            ),
        )))
        assertEquals(listOf("推导步骤", "任取 x₁<x₂", "f(x)=x²"), NativeClassroomText.lectureParagraphs(slide))
        assertEquals("任取 x₁小于x₂，f(x)等于x的平方", NativeClassroomText.forSpeech("任取 x₁<x₂，f(x)=x²"))
    }
}
