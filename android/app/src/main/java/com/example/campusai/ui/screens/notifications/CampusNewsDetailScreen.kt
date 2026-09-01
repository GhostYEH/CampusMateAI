package com.example.campusai.ui.screens.notifications

import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.CampusNews
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.*

private val CategoryBlue = Color(0xFF5368E8)
private val CategoryGreen = Color(0xFF35B99A)
private val CategoryOrange = Color(0xFFFFA43A)
private val CategoryPurple = Color(0xFF8B5CF6)

@Composable
fun CampusNewsDetailScreen(
    newsId: String,
    repository: AppRepository,
    onBack: () -> Unit,
) {
    val news = remember(newsId) { repository.getCampusNewsById(newsId) }
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()

    val animatedAlpha by animateFloatAsState(
        targetValue = 1f,
        animationSpec = tween(420, easing = CubicBezierEasing(0.2f, 0.8f, 0.2f, 1f)),
    )

    if (news == null) {
        Box(
            modifier = Modifier.fillMaxSize().background(Background).padding(32.dp),
            contentAlignment = Alignment.Center,
        ) {
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Icon(Icons.Default.Info, null, tint = Muted, modifier = Modifier.size(48.dp))
                Spacer(Modifier.height(12.dp))
                Text("未找到该动态", color = Muted, fontSize = 15.sp)
                Spacer(Modifier.height(8.dp))
                TextButton(onClick = onBack) { Text("返回首页") }
            }
        }
        return
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .graphicsLayer { alpha = animatedAlpha }
            .verticalScroll(rememberScrollState()),
    ) {
        // ─── 顶部头图区域 ───
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(220.dp)
                .background(CategoryBlue),
        ) {
            // 背景装饰
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .background(
                        Brush.verticalGradient(
                            0f to CategoryBlue,
                            0.5f to CategoryBlue.copy(alpha = 0.85f),
                            1f to CategoryBlue.copy(alpha = 0.4f),
                        ),
                    ),
            )
            // 装饰圆形
            Box(
                modifier = Modifier
                    .size(200.dp)
                    .align(Alignment.TopEnd)
                    .offset(x = 40.dp, y = (-40).dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.08f)),
            )
            Box(
                modifier = Modifier
                    .size(120.dp)
                    .align(Alignment.BottomStart)
                    .offset(x = (-20).dp, y = 20.dp)
                    .clip(CircleShape)
                    .background(Color.White.copy(alpha = 0.05f)),
            )

            // 来源标签
            Row(
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .padding(top = 8.dp, end = 16.dp)
                    .statusBarsPadding(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(Color.White.copy(alpha = 0.2f))
                        .padding(horizontal = 12.dp, vertical = 5.dp),
                ) {
                    Text(news.source, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                }
            }

            // 底部标题区域
            Column(
                modifier = Modifier
                    .align(Alignment.BottomStart)
                    .padding(start = 22.dp, end = 22.dp, bottom = 22.dp),
            ) {
                // 分类标签
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(Color.White.copy(alpha = 0.25f))
                        .padding(horizontal = 10.dp, vertical = 3.dp),
                ) {
                    Text(news.category, color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.SemiBold)
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    news.title,
                    color = Color.White,
                    fontSize = 22.sp,
                    fontWeight = FontWeight.Bold,
                    lineHeight = 28.sp,
                    letterSpacing = (-0.3).sp,
                )
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.Schedule, null, tint = Color.White.copy(alpha = 0.8f), modifier = Modifier.size(13.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(news.time, color = Color.White.copy(alpha = 0.8f), fontSize = 11.sp)
                }
            }
        }

        // ─── 内容卡片区域 ───
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .offset(y = (-16).dp)
                .clip(RoundedCornerShape(topStart = 24.dp, topEnd = 24.dp))
                .background(Surface)
                .padding(22.dp)
                .animateContentSize(),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            // 摘要区
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(12.dp))
                    .background(cardBackground(news.category))
                    .padding(14.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(
                        Icons.Default.AutoStories,
                        null,
                        tint = CategoryBlue,
                        modifier = Modifier.size(16.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text("摘要", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = CategoryBlue)
                }
                Spacer(Modifier.height(6.dp))
                Text(news.summary, color = TextPrimary, fontSize = 14.sp, lineHeight = 21.sp)
            }

            // 正文
            Column(modifier = Modifier.enterAnimation(delayMs = 60, enabled = !reduceMotion)) {
                Text("详细内容", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
                Spacer(Modifier.height(8.dp))
                Text(
                    news.content,
                    color = TextPrimary,
                    fontSize = 14.sp,
                    lineHeight = 24.sp,
                    letterSpacing = 0.1.sp,
                )
            }

            // 标签区
            if (news.tags.isNotEmpty()) {
                Column(modifier = Modifier.padding(top = 4.dp)) {
                    Text("相关标签", fontSize = 12.sp, color = Muted)
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        news.tags.forEach { tag ->
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .border(1.dp, Line, RoundedCornerShape(6.dp))
                                    .padding(horizontal = 10.dp, vertical = 5.dp),
                            ) {
                                Text(tag, fontSize = 11.sp, color = Muted)
                            }
                        }
                    }
                }
            }

            // 关联待办
            if (news.relatedTasks.isNotEmpty()) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(12.dp))
                        .border(1.dp, Line, RoundedCornerShape(12.dp))
                        .padding(14.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.CheckCircle, null, tint = CategoryOrange, modifier = Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text("相关事项", fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = CategoryOrange)
                    }
                    Spacer(Modifier.height(8.dp))
                    news.relatedTasks.forEach { task ->
                        Row(
                            modifier = Modifier.padding(vertical = 3.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(6.dp)
                                    .clip(CircleShape)
                                    .background(CategoryOrange),
                            )
                            Spacer(Modifier.width(8.dp))
                            Text(task, fontSize = 13.sp, color = TextPrimary)
                        }
                    }
                }
            }

            Spacer(Modifier.height(4.dp))

            // 底部来源信息
            Divider(color = Line, thickness = 1.dp)
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column {
                    Text("发布来源", fontSize = 10.sp, color = Muted)
                    Text(news.source, fontSize = 12.sp, color = TextPrimary, fontWeight = FontWeight.Medium)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("发布时间", fontSize = 10.sp, color = Muted)
                    Text(news.time, fontSize = 12.sp, color = TextPrimary)
                }
            }

            Spacer(Modifier.height(16.dp))
        }
    }
}

@Composable
private fun cardBackground(category: String): Color {
    return when {
        category.contains("学习") || category.contains("考试") ->
            Color(0xFF5368E8).copy(alpha = 0.06f)
        category.contains("创新") || category.contains("比赛") ->
            Color(0xFFFFA43A).copy(alpha = 0.06f)
        category.contains("心理") || category.contains("活动") ->
            Color(0xFF8B5CF6).copy(alpha = 0.06f)
        else -> Color(0xFF35B99A).copy(alpha = 0.06f)
    }
}
