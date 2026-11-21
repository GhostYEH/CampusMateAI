package com.example.campusai.ui.screens.courses.nativeplayer

import com.example.campusai.data.classroom.nativeplayer.NativeCanvasElement
import com.example.campusai.data.classroom.nativeplayer.NativeSlide
import java.util.Locale

private const val Chalk = "#F4ECD9"
private const val ChalkSoft = "#DCEAE3"
private const val ChalkMuted = "#AAC5B9"
private const val Brass = "#EDBE80"
private const val Card = "#284B4D"
private const val CardOutline = "#547B72"

private val TemplateTextColors = mapOf(
    "#1f2937" to Chalk,
    "#374151" to ChalkSoft,
    "#6b7280" to ChalkMuted,
    "#722ed1" to Brass,
)

/** Apply the classroom palette to the generator's stock canvas at render time. */
internal fun classroomSlideTemplate(slide: NativeSlide): NativeSlide {
    val background = slide.background
    val stockSurface = background.color.equals("#ffffff", ignoreCase = true)
    val stockInk = slide.theme.fontColor.equals("#1f2937", ignoreCase = true)
    val templateAccent = slide.elements.any {
        it is NativeCanvasElement.Shape && it.id == "el_accent" && it.fill.equals("#722ed1", ignoreCase = true)
    }
    if (!stockSurface || !stockInk || !templateAccent ||
        background.imageUrl != null || background.gradientColors.isNotEmpty() ||
        slide.elements.none { it is NativeCanvasElement.Text && it.id == "el_title" }
    ) {
        return slide
    }

    return slide.copy(
        background = background.copy(gradientColors = listOf("#203E41", "#11282E")),
        elements = slide.elements.map { element ->
            when (element) {
                is NativeCanvasElement.Text -> {
                    val color = TemplateTextColors[element.fontColor?.lowercase(Locale.ROOT)]
                    if (color == null) element else element.copy(fontColor = color)
                }
                is NativeCanvasElement.Shape -> when (element.fill?.lowercase(Locale.ROOT)) {
                    "#722ed1" -> element.copy(fill = Brass, radius = 3.0)
                    "#f5f3ff" -> element.copy(fill = Card, stroke = element.stroke ?: CardOutline,
                        strokeWidth = element.strokeWidth.takeIf { it > 0.0 } ?: 1.0,
                        radius = element.radius.takeIf { it > 0.0 } ?: 12.0)
                    else -> element
                }
                else -> element
            }
        },
    )
}
