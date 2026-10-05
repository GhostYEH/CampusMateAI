package com.example.campusai.ui.screens.tasks

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp

internal val JournalInk = Color(0xFF183F39)
internal val JournalPaper = Color(0xFFF7F2E8)
internal val JournalMuted = Color(0xFF64746E)
internal val JournalAmber = Color(0xFFC58B55)

internal fun Modifier.journalPaper(shape: Shape = RoundedCornerShape(24.dp)): Modifier =
    this.clip(shape)
        .background(Brush.linearGradient(listOf(Color(0xFFFFFBF2), JournalPaper, Color(0xFFECE8DC))))
        .border(1.dp, Color(0x66CFBDA4), shape)
        .drawBehind {
            for (row in 0..9) for (column in 0..13) {
                drawCircle(Color(0x0DBB9773), .55.dp.toPx(), Offset(size.width * (column + .4f) / 14f, size.height * (row + .5f) / 10f))
            }
        }

/** A quiet desk-light backdrop, drawn locally so the task pages have their own scene. */
@Composable
internal fun JournalBackdrop(modifier: Modifier = Modifier) {
    Box(modifier.background(Brush.verticalGradient(listOf(Color(0xFF12283D), Color(0xFF24443D), Color(0xFF423C37))))) {
        Canvas(Modifier.matchParentSize()) {
            drawCircle(
                brush = Brush.radialGradient(
                    listOf(Color(0x55DFA76A), Color.Transparent),
                    center = Offset(size.width * .86f, size.height * .12f),
                    radius = size.width * .75f,
                ),
                radius = size.width * .75f,
                center = Offset(size.width * .86f, size.height * .12f),
            )
            val line = Color(0x24D7BA91)
            val baseline = size.height * .71f
            drawLine(line, Offset(0f, baseline), Offset(size.width, baseline - size.height * .08f), 1.dp.toPx())
            drawLine(line, Offset(0f, baseline + 18.dp.toPx()), Offset(size.width, baseline - size.height * .08f + 18.dp.toPx()), 1.dp.toPx())
            for (row in 0..16) for (column in 0..9) {
                val x = size.width * (column + .35f) / 10f
                val y = size.height * (row + .45f) / 17f
                drawCircle(Color(0x15FFF1D7), .7.dp.toPx(), Offset(x, y))
            }
        }
    }
}

/** Warm paper with a fine ruled edge and a light printed grain. */
@Composable
internal fun JournalSheet(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    val shape = RoundedCornerShape(20.dp)
    Box(
        modifier.clip(shape)
            .background(Brush.linearGradient(listOf(Color(0xFFFFFBF2), JournalPaper, Color(0xFFECE8DC))))
            .border(1.dp, Color(0x66CFBDA4), shape),
    ) {
        Canvas(Modifier.matchParentSize()) {
            drawLine(Color(0x44BD9D76), Offset(12.dp.toPx(), 0f), Offset(12.dp.toPx(), size.height), .8.dp.toPx())
            for (row in 0..7) for (column in 0..11) {
                val x = size.width * (column + .5f) / 12f
                val y = size.height * (row + .5f) / 8f
                drawCircle(Color(0x0DBB9773), .65.dp.toPx(), Offset(x, y))
            }
        }
        content()
    }
}

@Composable
internal fun PaperPlusButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier.size(48.dp).semantics { contentDescription = "新增个人待办" }.clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(37.dp)) {
            val fold = 9.dp.toPx()
            val page = Path().apply {
                moveTo(1.dp.toPx(), 1.dp.toPx())
                lineTo(size.width - fold, 1.dp.toPx())
                lineTo(size.width - 1.dp.toPx(), fold)
                lineTo(size.width - 1.dp.toPx(), size.height - 1.dp.toPx())
                lineTo(1.dp.toPx(), size.height - 1.dp.toPx())
                close()
            }
            drawPath(page, Color(0xFFF7EBD5))
            drawPath(page, Color(0xFFDBB985), style = Stroke(1.dp.toPx()))
            drawLine(Color(0xFFDBB985), Offset(size.width - fold, 1.dp.toPx()), Offset(size.width - fold, fold), 1.dp.toPx())
            drawLine(Color(0xFFDBB985), Offset(size.width - fold, fold), Offset(size.width - 1.dp.toPx(), fold), 1.dp.toPx())
        }
        Icon(Icons.Default.Add, null, tint = JournalInk, modifier = Modifier.size(22.dp).graphicsLayer { translationY = 2.dp.toPx() })
    }
}
