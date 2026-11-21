package com.example.campusai.ui.screens.courses.nativeplayer

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.classroom.nativeplayer.NativePblProject
import com.example.campusai.data.classroom.nativeplayer.NativePblTask
import com.example.campusai.ui.theme.Accent
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

@Composable
fun NativePblPanel(
    project: NativePblProject,
    hasFallback: Boolean,
    onOpenFallback: () -> Unit,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(Surface, RoundedCornerShape(14.dp))
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(project.title, color = TextPrimary, fontSize = 20.sp, fontWeight = FontWeight.Bold)
            if (project.instructorName != null) {
                Text("指导：${project.instructorName}", color = Muted, fontSize = 12.sp)
            }
            Spacer(Modifier.height(6.dp))
            Text(project.description, color = TextPrimary, fontSize = 13.sp, lineHeight = 20.sp)
        }
        items(project.milestones.size) { index ->
            val milestone = project.milestones[index]
            Column(
                Modifier
                    .fillMaxWidth()
                    .border(1.dp, Line, RoundedCornerShape(12.dp))
                    .background(Color(0xFFFFFEF8), RoundedCornerShape(12.dp))
                    .padding(14.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "阶段 ${index + 1}",
                        color = Primary,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier
                            .background(PrimarySoft, RoundedCornerShape(6.dp))
                            .padding(horizontal = 8.dp, vertical = 4.dp),
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        milestone.title,
                        color = TextPrimary,
                        fontSize = 15.sp,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        statusText(milestone.status),
                        color = statusColor(milestone.status),
                        fontSize = 11.sp,
                    )
                }
                if (milestone.description.isNotBlank()) {
                    Spacer(Modifier.height(6.dp))
                    Text(milestone.description, color = Muted, fontSize = 12.sp, lineHeight = 18.sp)
                }
                milestone.tasks.forEach { task ->
                    TaskRow(task)
                }
            }
        }
        item {
            Text(
                "项目任务的提交与评价仍由受管工作台处理；本页保留原任务、提示和阶段状态，可继续在兼容工作台完成产出。",
                color = Muted,
                fontSize = 12.sp,
                lineHeight = 18.sp,
                modifier = Modifier
                    .fillMaxWidth()
                    .background(Color(0xFFF2F4EC), RoundedCornerShape(8.dp))
                    .padding(10.dp),
            )
            if (hasFallback) {
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = onOpenFallback, modifier = Modifier.fillMaxWidth()) {
                    Text("打开兼容工作台继续项目")
                }
            }
        }
    }
}

@Composable
private fun TaskRow(task: NativePblTask) {
    Column(
        Modifier
            .fillMaxWidth()
            .padding(top = 8.dp)
            .background(Color(0xFFF7F8F2), RoundedCornerShape(8.dp))
            .padding(10.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.size(6.dp).background(statusColor(task.status), RoundedCornerShape(3.dp))) {}
            Spacer(Modifier.width(8.dp))
            Text(task.title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.Medium)
            Spacer(Modifier.weight(1f))
            Text(statusText(task.status), color = statusColor(task.status), fontSize = 10.sp)
        }
        if (task.description.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(task.description, color = Muted, fontSize = 11.sp, lineHeight = 16.sp)
        }
        if (task.hints.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            Text("提示：${task.hints.joinToString("；")}", color = Accent, fontSize = 11.sp, lineHeight = 16.sp)
        }
    }
}

private fun statusText(status: String): String = when (status) {
    "completed", "done" -> "已完成"
    "in_progress", "active" -> "进行中"
    "locked" -> "未解锁"
    else -> "待开始"
}

@Composable
private fun statusColor(status: String): Color = when (status) {
    "completed", "done" -> Success
    "in_progress", "active" -> Accent
    else -> Muted
}
