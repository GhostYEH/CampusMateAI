package com.example.campusai.ui.screens.courses

import androidx.compose.animation.core.*
import androidx.compose.foundation.border
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.ModeBadge
import com.example.campusai.ui.theme.*

@Composable
fun CoursesScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val courses = listOf("数据结构", "计算机组成原理", "高等数学（下）", "大学英语 IV", "操作系统原理", "计算机网络")
    val codes = listOf("DS", "CO", "MA", "EN", "OS", "CN")
    val teachers = listOf("张明远", "刘文静", "王建国")

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(400, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f))
    )

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp)
            .graphicsLayer { alpha = animatedAlpha },
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text("课程中心", style = MaterialTheme.typography.headlineMedium)
                    Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
                }
                ModeBadge(mockMode)
            }
        }

        itemsIndexed(courses) { i, course ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Surface)
                    .border(1.dp, Line, RoundedCornerShape(10.dp))
                    .padding(18.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(48.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(PrimarySoft),
                    contentAlignment = Alignment.Center
                ) {
                    Text(codes[i], fontWeight = FontWeight.Bold, color = Primary, fontSize = 16.sp)
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        if (i % 2 == 0) "专业必修课" else "专业基础课",
                        color = Muted, fontSize = 11.sp
                    )
                    Text(course, fontWeight = FontWeight.SemiBold, fontSize = 16.sp)
                    Text(
                        "${teachers[i % 3]}老师 · 教学楼 ${2 + i}-30${i}",
                        color = Muted, fontSize = 12.sp
                    )
                }
                OutlinedButton(
                    onClick = { },
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Primary)
                ) {
                    Text("进入课程", fontSize = 12.sp)
                    Icon(Icons.Default.ChevronRight, null, modifier = Modifier.size(14.dp))
                }
            }
        }
    }
}

