package com.example.campusai.ui.screens.courses

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R

internal val ClassroomNight = Color(0xFF182638)
internal val ClassroomChalk = Color(0xFFF2E9D3)
internal val ClassroomAmber = Color(0xFFDAB27A)
internal val ClassroomWood = Color(0xFFAD7A50)
private val Board = Color(0xFF172E38)
private val BoardMuted = Color(0xFFB9CAC4)

@Composable
internal fun ClassroomStageBackdrop(modifier: Modifier = Modifier) {
    Box(modifier.background(ClassroomNight)) {
        Image(painterResource(R.drawable.classroom_evening_interior), null,
            Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.matchParentSize().background(Brush.verticalGradient(listOf(
            Color(0x4D101D2B), Color(0x66101D2B), Color(0xB5182638)))))
    }
}

@Composable
internal fun LessonBlackboard(
    topic: String,
    onTopicChange: (String) -> Unit,
    teachingStyle: String,
    onTeachingStyleChange: (String) -> Unit,
    materialName: String?,
    uploading: Boolean,
    onPickMaterial: () -> Unit,
    onRemoveMaterial: () -> Unit,
) {
    val frame = RoundedCornerShape(13.dp)
    Column(Modifier.fillMaxWidth().border(5.dp, ClassroomWood, frame)
        .background(Color(0xFF5B4436), frame).padding(3.dp)
        .clip(RoundedCornerShape(7.dp))
        .background(Brush.verticalGradient(listOf(Color(0xFF203D45), Board, Color(0xFF112A34))))
        .drawBehind {
            for (row in 0..7) for (column in 0..9) {
                drawCircle(Color(0x0DF2E9D3), .65.dp.toPx(),
                    Offset(size.width * (column + .4f) / 10f, size.height * (row + .5f) / 8f))
            }
        }
        .padding(19.dp)) {
        Text("01  /  提出问题", color = ClassroomAmber,
            fontSize = 10.sp, letterSpacing = 1.3.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(13.dp))
        Text("今天想弄懂什么？", color = ClassroomChalk, fontSize = 24.sp, fontWeight = FontWeight.Bold)
        Text("写下一个问题，老师会陪你一步步探索。", color = BoardMuted, fontSize = 12.sp)
        Spacer(Modifier.height(18.dp))
        Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(5.dp)).background(Color(0x66213A46))
            .border(1.dp, Color(0x668EAAA3), RoundedCornerShape(5.dp)).padding(13.dp)) {
            BasicTextField(
                value = topic,
                onValueChange = { onTopicChange(it.take(500)) },
                modifier = Modifier.fillMaxWidth().heightIn(min = 73.dp),
                textStyle = TextStyle(color = ClassroomChalk, fontSize = 17.sp, lineHeight = 25.sp),
                cursorBrush = SolidColor(ClassroomAmber),
                maxLines = 5,
                decorationBox = { inner ->
                    Box {
                        if (topic.isEmpty()) Text("例如：Linux 文件权限到底怎么用？",
                            color = BoardMuted.copy(alpha = .72f), fontSize = 14.sp)
                        inner()
                    }
                },
            )
        }
        if (topic.isBlank()) {
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(top = 9.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("Python 列表和字典的区别", "怎样理解 Linux 文件权限").forEach { example ->
                    Text(example, Modifier.clip(RoundedCornerShape(3.dp))
                        .border(1.dp, Color(0x557D9C98), RoundedCornerShape(3.dp))
                        .clickable { onTopicChange(example) }.padding(horizontal = 9.dp, vertical = 7.dp),
                        color = BoardMuted, fontSize = 11.sp, maxLines = 1)
                }
            }
        }
        BoardDivider()
        Text("02  选择讲法", color = ClassroomChalk, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) {
            listOf(Triple("循序讲解", "↗", "从基础讲起"),
                Triple("启发提问", "?", "边想边回答"),
                Triple("例题练习", "∑", "通过例题掌握")).forEach { (label, symbol, hint) ->
                val active = teachingStyle == label
                Column(Modifier.weight(1f).clip(RoundedCornerShape(5.dp))
                    .background(if (active) Color(0x334B6C79) else Color.Transparent)
                    .border(1.dp, if (active) ClassroomAmber else Color(0x557D9C98), RoundedCornerShape(5.dp))
                    .clickable { onTeachingStyleChange(label) }.padding(horizontal = 5.dp, vertical = 9.dp),
                    horizontalAlignment = Alignment.CenterHorizontally) {
                    Text(symbol, color = if (active) ClassroomAmber else BoardMuted,
                        fontSize = 23.sp, fontWeight = FontWeight.Bold)
                    Text(label, color = ClassroomChalk, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                        maxLines = 1)
                    Text(hint, color = BoardMuted, fontSize = 9.sp, maxLines = 1)
                }
            }
        }
        Text(when (teachingStyle) {
            "启发提问" -> "老师会通过连续提问，引导你自己找到答案。"
            "例题练习" -> "先看示例，再通过练习巩固这道题。"
            else -> "从基础到应用，循着清楚的步骤慢慢讲。"
        }, Modifier.padding(top = 9.dp), color = BoardMuted, fontSize = 11.sp)
        BoardDivider()
        Text("03  带上讲义", color = ClassroomChalk, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(10.dp))
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(5.dp))
            .background(Color(0xFFE8D9BC)).padding(horizontal = 8.dp, vertical = 5.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Row(Modifier.weight(1f).clickable(enabled = !uploading, onClick = onPickMaterial)
                .padding(horizontal = 4.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.AttachFile, null, Modifier.size(20.dp), tint = ClassroomNight)
                Spacer(Modifier.width(9.dp))
                Column(Modifier.weight(1f)) {
                    Text(materialName ?: if (uploading) "正在读取资料…" else "添加自己的学习资料",
                        color = ClassroomNight, fontSize = 13.sp, fontWeight = FontWeight.Bold,
                        maxLines = 1, overflow = TextOverflow.Ellipsis)
                    Text(if (materialName == null) "PDF / Word / TXT / Markdown · 不超过 2 MB" else "点此更换讲义",
                        color = Color(0xFF52606A), fontSize = 10.sp, maxLines = 1)
                }
                if (materialName == null) Text("＋", color = ClassroomNight, fontSize = 22.sp)
            }
            if (materialName != null) Box(Modifier.size(36.dp).clip(CircleShape)
                .clickable(onClick = onRemoveMaterial), contentAlignment = Alignment.Center) {
                Icon(Icons.Default.Close, "移除讲义", Modifier.size(17.dp), tint = ClassroomNight)
            }
        }
    }
}

@Composable
private fun BoardDivider() {
    Spacer(Modifier.height(19.dp))
    Box(Modifier.fillMaxWidth().height(1.dp).background(Color(0x447FA098)))
    Spacer(Modifier.height(17.dp))
}

@Composable
internal fun ClassroomStartDock(enabled: Boolean, submitting: Boolean, onStart: () -> Unit) {
    Column(Modifier.fillMaxWidth().background(Color(0xF21A2A36))
        .drawBehind { drawLine(ClassroomWood.copy(alpha = .7f), Offset.Zero,
            Offset(size.width, 0f), 1.dp.toPx()) }.padding(start = 20.dp, end = 20.dp, top = 10.dp, bottom = 8.dp)) {
        Button(onClick = onStart, enabled = enabled, modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(6.dp),
            colors = ButtonDefaults.buttonColors(containerColor = ClassroomAmber, contentColor = ClassroomNight,
                disabledContainerColor = Color(0xFF788078), disabledContentColor = Color(0xFFE2E0D4))) {
            Icon(Icons.Default.PlayArrow, null, Modifier.size(21.dp))
            Spacer(Modifier.width(6.dp))
            Text(if (submitting) "正在准备…" else "生成我的课堂", fontSize = 15.sp, fontWeight = FontWeight.Bold)
        }
    }
}
