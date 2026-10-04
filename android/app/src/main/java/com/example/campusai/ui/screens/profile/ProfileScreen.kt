package com.example.campusai.ui.screens.profile

import com.example.campusai.ui.components.GlassTextButton as TextButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
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
import com.example.campusai.ui.theme.*

@Composable
fun ProfileScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit,
) {
    val session by repository.session.collectAsStateWithLifecycle()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    var showAbout by remember { mutableStateOf(false) }

    Box(Modifier.fillMaxSize().background(Color(0xFF14243D))) {
        Image(painterResource(R.drawable.campus_twilight_original), contentDescription = null,
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        Box(Modifier.fillMaxSize().background(Color(0xA4132634)))
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(
                bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding() + 26.dp,
            ),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            item {
                ProfileHero(
                    name = session?.name ?: "林知夏",
                    detail = session?.detail ?: "计算机科学与技术 · 大三",
                    reduceMotion = reduceMotion,
                    onBack = { onNavigate("home") },
                    onAccount = { onNavigate("account") },
                    onFavorites = { onNavigate("favorites") },
                    onSettings = { onNavigate("settings") },
                    onScan = { onNavigate("qr_scanner") },
                )
            }
            item {
                Text(
                    "更多服务",
                    color = Color(0xFFFFECD0),
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    modifier = Modifier.padding(start = 20.dp, top = 2.dp),
                )
            }
            item {
                ProfileMenu(
                    modifier = Modifier.enterAnimation(delayMs = 130, enabled = !reduceMotion),
                    rows = listOf(
                        ProfileRow(Icons.Default.Description, "我的文件", "查看保存的资料") { onNavigate("files") },
                        ProfileRow(Icons.Default.NotificationsActive, "系统消息", "查看账号与校园消息") { onNavigate("notifications") },
                        ProfileRow(Icons.Default.Security, "隐私与数据", "查看权限、通知与数据说明") { onNavigate("settings") },
                        ProfileRow(Icons.Default.HeadsetMic, "帮助与反馈", "常见问题、问题反馈与服务状态") { onNavigate("help-feedback") },
                        ProfileRow(Icons.Default.Info, "关于 CampusMate", "版本与能力边界") { showAbout = true },
                    ),
                )
            }
        }
    }

    if (showAbout) {
        AlertDialog(
            onDismissRequest = { showAbout = false },
            containerColor = Surface,
            iconContentColor = Primary,
            titleContentColor = TextPrimary,
            textContentColor = Muted,
            icon = { Icon(Icons.Default.AutoAwesome, null) },
            title = { Text("关于 CampusMate") },
            text = {
                Text("面向大学生的成长型智能陪伴助手。CPM 的回答仅作辅助建议，学校正式通知为准。")
            },
            confirmButton = {
                TextButton(onClick = { showAbout = false }) {
                    Text("知道了", color = Primary)
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
    onBack: () -> Unit,
    onAccount: () -> Unit,
    onFavorites: () -> Unit,
    onSettings: () -> Unit,
    onScan: () -> Unit,
) {
    Box(
        Modifier.fillMaxWidth().height(382.dp)
            .enterAnimation(enabled = !reduceMotion),
    ) {
        Box(
            Modifier.fillMaxWidth().height(318.dp)
                .clip(RoundedCornerShape(bottomStart = 30.dp, bottomEnd = 30.dp))
                .background(
                    Brush.verticalGradient(listOf(Color(0xD0172747), Color(0xC11E3553), Color(0x8B172747))),
                ),
        ) {
            HeroDecorations()
            Column(
                Modifier.fillMaxSize().statusBarsPadding()
                    .padding(start = 24.dp, top = 15.dp, end = 20.dp),
            ) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            IconButton(onClick = onBack, modifier = Modifier.size(42.dp)
                                .background(Color(0xAA203B45), CircleShape)) {
                                Icon(Icons.Default.ArrowBack, contentDescription = "返回校园", tint = Color.White)
                            }
                            Spacer(Modifier.width(10.dp))
                            Text("我的", color = Color.White, fontSize = 28.sp, fontWeight = FontWeight.Bold)
                        }
                        Text("今天也照顾好自己的节奏", color = Color.White.copy(alpha = .74f), fontSize = 11.sp)
                    }
                    Spacer(Modifier.weight(1f))
                    Box(
                        Modifier.size(40.dp).clip(CircleShape).background(Color.White.copy(alpha = .12f))
                            .campusClickable(onClick = onScan),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.CropFree, "扫一扫", tint = Color.White, modifier = Modifier.size(22.dp))
                    }
                }
                Spacer(Modifier.height(30.dp))
                Row(
                    Modifier.fillMaxWidth().campusClickable(onClick = onAccount),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    ReferenceAvatar(82.dp)
                    Column(Modifier.padding(start = 17.dp).weight(1f)) {
                        Text(
                            name,
                            color = Color.White,
                            fontSize = 24.sp,
                            fontWeight = FontWeight.Bold,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(7.dp))
                        Text(
                            detail.ifBlank { "计算机科学与技术 · 大三" },
                            color = Color.White.copy(alpha = .84f),
                            fontSize = 14.sp,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Spacer(Modifier.height(9.dp))
                        Row(
                            Modifier.clip(CircleShape).background(Color.White.copy(alpha = .12f))
                                .padding(horizontal = 9.dp, vertical = 5.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.size(6.dp).clip(CircleShape).background(Color(0xFF9BE1C0)))
                            Spacer(Modifier.width(6.dp))
                            Text("点击查看和编辑个人资料", color = Color.White.copy(alpha = .88f), fontSize = 9.sp)
                        }
                    }
                    Icon(Icons.Default.ChevronRight, null, tint = Color.White.copy(alpha = .8f))
                }
            }
        }
        ProfileQuickActions(
            modifier = Modifier.align(Alignment.BottomCenter).padding(horizontal = 16.dp),
            onAccount = onAccount,
            onFavorites = onFavorites,
            onSettings = onSettings,
        )
    }
}

@Composable
private fun HeroDecorations() {
    Canvas(Modifier.fillMaxSize()) {
        drawCircle(
            Color.White.copy(alpha = .055f),
            radius = size.width * .27f,
            center = Offset(size.width * .95f, size.height * .03f),
        )
        drawCircle(
            Color.White.copy(alpha = .07f),
            radius = size.width * .065f,
            center = Offset(size.width * .76f, size.height * .43f),
        )
        repeat(5) { x ->
            repeat(3) { y ->
                drawCircle(
                    Color.White.copy(alpha = .12f),
                    radius = 2.8f,
                    center = Offset(size.width * .84f + x * 17f, size.height * .72f + y * 17f),
                )
            }
        }
    }
}

@Composable
private fun ProfileQuickActions(
    modifier: Modifier = Modifier,
    onAccount: () -> Unit,
    onFavorites: () -> Unit,
    onSettings: () -> Unit,
) {
    val actions = listOf(
        QuickAction(Icons.Default.Person, "资料", onAccount),
        QuickAction(Icons.Default.Bookmark, "收藏", onFavorites),
        QuickAction(Icons.Default.Settings, "设置", onSettings),
    )
    Row(
        modifier.fillMaxWidth().height(126.dp)
            .clip(RoundedCornerShape(24.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .7f), RoundedCornerShape(24.dp))
            .padding(horizontal = 7.dp, vertical = 16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        actions.forEachIndexed { index, action ->
            Column(
                Modifier.weight(1f).fillMaxHeight().clip(RoundedCornerShape(16.dp))
                    .campusClickable(onClick = action.onClick),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Box(
                    Modifier.size(43.dp).clip(RoundedCornerShape(14.dp))
                        .background(if (index == 1) Accent.copy(alpha = .12f) else PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        action.icon,
                        null,
                        tint = if (index == 1) Accent else Primary,
                        modifier = Modifier.size(23.dp),
                    )
                }
                Spacer(Modifier.height(9.dp))
                Text(action.label, color = TextPrimary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }
}

private data class QuickAction(val icon: ImageVector, val label: String, val onClick: () -> Unit)
private data class ProfileRow(
    val icon: ImageVector,
    val label: String,
    val subtitle: String,
    val onClick: () -> Unit,
)

@Composable
private fun ProfileMenu(rows: List<ProfileRow>, modifier: Modifier = Modifier) {
    Column(
        modifier.padding(horizontal = 16.dp).fillMaxWidth()
            .clip(RoundedCornerShape(22.dp)).background(Surface)
            .border(1.dp, Line.copy(alpha = .7f), RoundedCornerShape(22.dp))
            .padding(horizontal = 16.dp, vertical = 3.dp),
    ) {
        rows.forEachIndexed { index, row ->
            Row(
                Modifier.fillMaxWidth().height(70.dp).campusClickable(onClick = row.onClick),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(row.icon, null, tint = Primary, modifier = Modifier.size(29.dp))
                Text(
                    row.label,
                    color = TextPrimary,
                    fontSize = 16.sp,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.padding(start = 18.dp).weight(1f),
                )
                Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(21.dp))
            }
            if (index != rows.lastIndex) {
                HorizontalDivider(color = Line, modifier = Modifier.padding(start = 53.dp))
            }
        }
    }
}

@Composable
internal fun ReferenceAvatar(size: Dp) {
    Box(
        Modifier.size(size).clip(CircleShape).background(Surface).padding(3.dp),
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
    Text(text, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold)
}

internal val ReferencePrimary: Color @Composable get() = Primary
internal val ReferencePrimarySoft: Color @Composable get() = PrimarySoft
internal val ReferenceSurface: Color @Composable get() = Surface
internal val ReferencePageBackground: Color @Composable get() = Background
internal val ReferenceText: Color @Composable get() = TextPrimary
internal val ReferenceMuted: Color @Composable get() = Muted
internal val ReferenceDivider: Color @Composable get() = Line
