package com.example.campusai.ui.screens.generic

import androidx.lifecycle.compose.collectAsStateWithLifecycle

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
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*

@Composable
fun GenericScreen(repository: AppRepository, section: String) {
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val titleMap = mapOf(
        "publish" to "发布中心",
        "stats" to "教学统计",
        "system" to "系统状态"
    )
    val titles = listOf("关键指标概览", "近期活动", "待处理事项", "运行状态")
    val icons = listOf(Icons.Default.BarChart, Icons.Default.History, Icons.Default.Description, Icons.Default.MonitorHeart)
    val values = listOf("96", "24", "6", "正常")
    val subtitles = listOf(
        if (section == "system") "系统服务数据" else if (section == "stats") "教学数据" else "当前模块数据"
    )

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
                    Text(titleMap[section] ?: "校园服务", style = MaterialTheme.typography.headlineMedium)
                    Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
                }
                ModeBadge(mockMode)
            }
        }

        itemsIndexed(titles) { i, title ->
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Surface)
                    .border(1.dp, Line, RoundedCornerShape(10.dp))
                    .padding(14.dp)
                    .enterAnimation(delayMs = i * 80, enabled = !reduceMotion),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(title, style = MaterialTheme.typography.titleSmall)
                    Icon(icons[i], null, tint = Muted, modifier = Modifier.size(20.dp))
                }
                Column(
                    modifier = Modifier.fillMaxWidth().height(120.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center
                ) {
                    Text(values[i], fontSize = 32.sp, fontWeight = FontWeight.Bold, color = Primary)
                    Text(subtitles[0], color = Muted, fontSize = 12.sp)
                }
            }
        }
    }
}

