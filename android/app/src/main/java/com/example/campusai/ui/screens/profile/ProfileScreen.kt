package com.example.campusai.ui.screens.profile

import android.app.Activity
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import androidx.core.view.WindowCompat
import kotlinx.coroutines.launch

private val ProfilePurple = Color(0xFF686BF7)
private val ProfilePurpleDark = Color(0xFF5E69F5)
private val ProfilePurpleLight = Color(0xFF8883FA)
private val ProfileBackground = Color(0xFFF8F9FD)
private val ProfileText = Color(0xFF151826)
private val ProfileMuted = Color(0xFF747B91)
private val ProfileLine = Color(0xFFEEF0F6)

@Composable
fun ProfileScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit,
) {
    val session by repository.session.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val darkMode by repository.darkMode.collectAsState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var showAbout by remember { mutableStateOf(false) }
    ReferenceSystemBars(darkMode)

    Box(Modifier.fillMaxSize().background(ProfileBackground)) {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ProfileHero(
                    name = session?.name ?: "林知夏",
                    detail = session?.detail ?: "计算机科学与技术 · 大三",
                    reduceMotion = reduceMotion,
                    onAccount = { onNavigate("account") },
                    onFiles = { onNavigate("courses") },
                    onActivities = { onNavigate("notifications") },
                    onFavorites = {
                        scope.launch { snackbar.showSnackbar("收藏内容会保存在本机") }
                    },
                    onSettings = { onNavigate("settings") },
                )
            }
            item {
                ProfileMenuCard(
                    modifier = Modifier.enterAnimation(delayMs = 140, enabled = !reduceMotion),
                    rows = listOf(
                        ProfileRow(Icons.Default.FolderOpen, "我的文件") { onNavigate("courses") },
                        ProfileRow(Icons.Default.EventAvailable, "我的活动") { onNavigate("notifications") },
                        ProfileRow(Icons.Default.Settings, "我的设置") { onNavigate("settings") },
                        ProfileRow(Icons.Default.HeadsetMic, "帮助与反馈") { onNavigate("counselor") },
                        ProfileRow(Icons.Default.Info, "关于我们") { showAbout = true },
                    ),
                )
            }
        }
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter).padding(16.dp))
    }

    if (showAbout) {
        AlertDialog(
            onDismissRequest = { showAbout = false },
            containerColor = Color.White,
            iconContentColor = ProfilePurple,
            titleContentColor = ProfileText,
            textContentColor = ProfileMuted,
            icon = { Icon(Icons.Default.AutoAwesome, null) },
            title = { Text("关于 CampusMate") },
            text = {
                Text("面向大学生的校园事务智能陪伴助手。当前 AI 导员与知识库能力会明确标注 Mock 模式。")
            },
            confirmButton = {
                TextButton(onClick = { showAbout = false }) {
                    Text("知道了", color = ProfilePurple)
                }
            },
        )
    }
}

@Composable
private fun ProfileHero(
    name: String,
    detail: String,
    reduceMotion: Boolean,
    onAccount: () -> Unit,
    onFiles: () -> Unit,
    onActivities: () -> Unit,
    onFavorites: () -> Unit,
    onSettings: () -> Unit,
) {
    Box(
        Modifier.fillMaxWidth().height(392.dp)
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            Modifier.fillMaxWidth().height(330.dp)
                .clip(RoundedCornerShape(bottomStart = 28.dp, bottomEnd = 28.dp))
                .background(
                    Brush.linearGradient(
                        0f to ProfilePurpleDark,
                        .55f to ProfilePurple,
                        1f to ProfilePurpleLight,
                        start = Offset.Zero,
                        end = Offset(1100f, 850f),
                    )
                ),
        ) {
            HeroDecorations()
            Column(
                Modifier.fillMaxSize().statusBarsPadding()
                    .padding(start = 28.dp, top = 20.dp, end = 24.dp),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        "我的",
                        color = Color.White,
                        fontSize = 29.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.weight(1f))
                    Icon(
                        Icons.Default.CropFree,
                        "扫一扫",
                        tint = Color.White,
                        modifier = Modifier.size(28.dp),
                    )
                }
                Spacer(Modifier.height(34.dp))
                Row(
                    Modifier.fillMaxWidth().campusClickable(onClick = onAccount),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ReferenceAvatar(88.dp)
                    Column(Modifier.padding(start = 18.dp).weight(1f)) {
                        Text(
                            name,
                            color = Color.White,
                            fontSize = 25.sp,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            detail.ifBlank { "计算机科学与技术 · 大三" },
                            color = Color.White.copy(alpha = .9f),
                            fontSize = 15.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    Icon(
                        Icons.Default.ChevronRight,
                        null,
                        tint = Color.White,
                        modifier = Modifier.size(28.dp),
                    )
                }
            }
        }
        ProfileQuickActions(
            modifier = Modifier.align(Alignment.BottomCenter).padding(horizontal = 16.dp),
            onFiles = onFiles,
            onActivities = onActivities,
            onFavorites = onFavorites,
            onSettings = onSettings,
        )
    }
}

@Composable
private fun HeroDecorations() {
    Canvas(Modifier.fillMaxSize()) {
        drawCircle(
            Color.White.copy(alpha = .08f),
            radius = size.width * .24f,
            center = Offset(size.width * .98f, size.height * .02f),
        )
        drawCircle(
            Color.White.copy(alpha = .09f),
            radius = size.width * .055f,
            center = Offset(size.width * .75f, size.height * .38f),
        )
        repeat(5) { x ->
            repeat(4) { y ->
                drawCircle(
                    Color.White.copy(alpha = .14f),
                    radius = 3.2f,
                    center = Offset(size.width * .86f + x * 19f, size.height * .71f + y * 19f),
                )
            }
        }
    }
}

@Composable
private fun ProfileQuickActions(
    modifier: Modifier = Modifier,
    onFiles: () -> Unit,
    onActivities: () -> Unit,
    onFavorites: () -> Unit,
    onSettings: () -> Unit,
) {
    val actions = listOf(
        QuickAction(Icons.Default.Description, "我的文件", onFiles),
        QuickAction(Icons.Default.EventAvailable, "我的活动", onActivities),
        QuickAction(Icons.Default.Star, "我的收藏", onFavorites),
        QuickAction(Icons.Default.Settings, "系统设置", onSettings),
    )
    Row(
        modifier.fillMaxWidth().height(132.dp)
            .shadow(
                elevation = 18.dp,
                shape = RoundedCornerShape(22.dp),
                ambientColor = Color(0x1A6670C8),
                spotColor = Color(0x246670C8),
            )
            .clip(RoundedCornerShape(22.dp))
            .background(Color.White)
            .padding(horizontal = 7.dp, vertical = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        actions.forEach { action ->
            Column(
                Modifier.weight(1f).fillMaxHeight().campusClickable(onClick = action.onClick),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    Modifier.size(43.dp).clip(RoundedCornerShape(14.dp))
                        .background(Color(0xFFF2F2FF)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        action.icon,
                        null,
                        tint = Color.White,
                        modifier = Modifier.size(25.dp).referenceIconGradient(),
                    )
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    action.label,
                    color = ProfileText,
                    fontSize = 13.sp,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                )
            }
        }
    }
}

private data class QuickAction(val icon: ImageVector, val label: String, val onClick: () -> Unit)
private data class ProfileRow(val icon: ImageVector, val label: String, val onClick: () -> Unit)

@Composable
private fun ProfileMenuCard(rows: List<ProfileRow>, modifier: Modifier = Modifier) {
    Column(
        modifier.padding(horizontal = 16.dp)
            .fillMaxWidth()
            .shadow(
                elevation = 14.dp,
                shape = RoundedCornerShape(22.dp),
                ambientColor = Color(0x126670C8),
                spotColor = Color(0x186670C8),
            )
            .clip(RoundedCornerShape(22.dp))
            .background(Color.White)
            .padding(horizontal = 18.dp, vertical = 4.dp),
    ) {
        rows.forEachIndexed { index, row ->
            Row(
                Modifier.fillMaxWidth().height(66.dp).campusClickable(onClick = row.onClick),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    row.icon,
                    null,
                    tint = Color.White,
                    modifier = Modifier.size(27.dp).referenceIconGradient(),
                )
                Text(
                    row.label,
                    color = ProfileText,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Normal,
                    modifier = Modifier.padding(start = 21.dp).weight(1f),
                )
                Icon(
                    Icons.Default.ChevronRight,
                    null,
                    tint = Color(0xFFAEB3C4),
                    modifier = Modifier.size(23.dp),
                )
            }
            if (index != rows.lastIndex) {
                HorizontalDivider(color = ProfileLine, modifier = Modifier.padding(start = 44.dp))
            }
        }
    }
}

@Composable
internal fun ReferenceAvatar(size: Dp) {
    Box(
        Modifier.size(size).clip(CircleShape).background(Color.White).padding(3.dp),
        contentAlignment = Alignment.Center,
    ) {
        Image(
            painter = painterResource(R.drawable.profile_avatar_reference),
            contentDescription = "个人头像",
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize().clip(CircleShape),
        )
    }
}

@Composable
internal fun ReferenceSectionLabel(text: String) {
    Text(text, color = ProfileText, fontSize = 15.sp, fontWeight = FontWeight.Bold)
}

internal val ReferencePrimary: Color get() = ProfilePurple
internal val ReferencePrimarySoft: Color get() = Color(0xFFF1F1FF)
internal val ReferenceSurface: Color get() = Color.White
internal val ReferencePageBackground: Color get() = ProfileBackground
internal val ReferenceText: Color get() = ProfileText
internal val ReferenceMuted: Color get() = ProfileMuted
internal val ReferenceDivider: Color get() = ProfileLine

private fun Modifier.referenceIconGradient(): Modifier =
    graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
        .drawWithCache {
            val gradient = Brush.linearGradient(
                colors = listOf(Color(0xFF557AF8), Color(0xFF745EF4)),
                start = Offset.Zero,
                end = Offset(size.width, size.height),
            )
            onDrawWithContent {
                drawContent()
                drawRect(gradient, blendMode = BlendMode.SrcIn)
            }
        }

@Composable
internal fun ReferenceSystemBars(darkMode: Boolean) {
    val view = LocalView.current
    DisposableEffect(view, darkMode) {
        val activity = view.context as? Activity
        val controller = activity?.let { WindowCompat.getInsetsController(it.window, view) }
        controller?.isAppearanceLightStatusBars = false
        controller?.isAppearanceLightNavigationBars = true
        onDispose {
            controller?.isAppearanceLightStatusBars = !darkMode
            controller?.isAppearanceLightNavigationBars = !darkMode
        }
    }
}
