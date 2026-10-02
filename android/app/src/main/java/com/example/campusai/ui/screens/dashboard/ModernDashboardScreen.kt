package com.example.campusai.ui.screens.dashboard

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowForwardIos
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.Menu
import androidx.compose.material.icons.filled.MenuBook
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.repository.AppRepository

private val WorldInk = Color(0xFF223045)
private val StudyAmber = Color(0xFFE7A837)
private val LibraryViolet = Color(0xFF7884ED)
private val GrowthGreen = Color(0xFF91BD6D)

/** A navigable campus scene. The illustration contains no baked-in controls or text. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ModernDashboardScreen(repository: AppRepository, onNavigate: (String) -> Unit) {
    var showMore by remember { mutableStateOf(false) }

    BoxWithConstraints(Modifier.fillMaxSize().background(WorldInk)) {
        Image(
            painter = painterResource(R.drawable.campus_world_scene),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier.fillMaxSize(),
        )
        Box(
            Modifier.fillMaxWidth().height(maxHeight * .19f).align(Alignment.TopCenter)
                .background(Brush.verticalGradient(listOf(Color(0xA51C3651), Color.Transparent))),
        )
        Box(
            Modifier.fillMaxWidth().height(maxHeight * .23f).align(Alignment.BottomCenter)
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color(0x9D152D43)))),
        )

        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(start = 22.dp, top = 20.dp, end = 18.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Column(Modifier.weight(1f)) {
                Text("CampusMate", color = Color.White, fontSize = 30.sp, fontWeight = FontWeight.Bold)
                Text("今天，学一点新东西", color = Color.White.copy(alpha = .91f), fontSize = 14.sp)
            }
            WorldIconButton(Icons.Default.Menu, "更多功能") { showMore = true }
            Spacer(Modifier.width(8.dp))
            WorldIconButton(Icons.Default.Person, "我的") { onNavigate("profile") }
        }

        // Buildings are touch targets too; the visible chips are not the only way in.
        WorldArea(
            "自习室", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .04f, y = maxHeight * .19f)
                .width(maxWidth * .53f).height(maxHeight * .25f),
        ) { onNavigate("focus") }
        WorldArea(
            "图书馆", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .59f, y = maxHeight * .32f)
                .width(maxWidth * .41f).height(maxHeight * .26f),
        ) { onNavigate("courses") }
        WorldArea(
            "成长墙", Modifier.align(Alignment.TopStart)
                .offset(x = 0.dp, y = maxHeight * .57f)
                .width(maxWidth * .47f).height(maxHeight * .18f),
        ) { onNavigate("focus_history") }
        WorldArea(
            "问小伴", Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .42f, y = maxHeight * .47f)
                .width(maxWidth * .18f).height(maxHeight * .11f),
        ) { onNavigate("counselor") }

        WorldDestination(
            label = "自习室", icon = Icons.Default.Timer, tint = StudyAmber,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .19f, y = maxHeight * .205f),
        ) { onNavigate("focus") }
        WorldDestination(
            label = "图书馆", icon = Icons.Default.MenuBook, tint = LibraryViolet,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .63f - 20.dp, y = maxHeight * .375f),
        ) { onNavigate("courses") }
        WorldDestination(
            label = "成长墙", icon = Icons.Default.History, tint = GrowthGreen,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = 18.dp, y = maxHeight * .525f),
        ) { onNavigate("focus_history") }
        WorldDestination(
            label = "问小伴", icon = Icons.Default.SmartToy, tint = LibraryViolet, compact = true,
            modifier = Modifier.align(Alignment.TopStart)
                .offset(x = maxWidth * .51f, y = maxHeight * .53f),
        ) { onNavigate("counselor") }

        Row(
            Modifier.align(Alignment.BottomCenter).navigationBarsPadding()
                .padding(start = 34.dp, end = 34.dp, bottom = 30.dp)
                .fillMaxWidth()
                .shadow(18.dp, CircleShape).clip(CircleShape)
                .background(Brush.horizontalGradient(listOf(Color(0xFF6D99F2), Color(0xFF7674E9))))
                .clickable(role = Role.Button) { onNavigate("focus") }
                .padding(vertical = 15.dp),
            horizontalArrangement = Arrangement.Center,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.AutoAwesome, null, tint = Color.White, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(10.dp))
            Text("开始学习", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            Spacer(Modifier.width(10.dp))
            Icon(Icons.Default.ArrowForwardIos, null, tint = Color.White, modifier = Modifier.size(14.dp))
        }
    }

    if (showMore) {
        ModalBottomSheet(onDismissRequest = { showMore = false }, containerColor = Color(0xFFF9FBF6)) {
            Column(Modifier.fillMaxWidth().padding(start = 22.dp, end = 22.dp, bottom = 28.dp)) {
                Text("更多功能", color = WorldInk, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text("学习之外的校园事务，随时可以在这里找到", color = Color(0xFF637183), fontSize = 13.sp)
                Spacer(Modifier.size(18.dp))
                MoreDestination("待办事项", Icons.Default.Timer) { showMore = false; onNavigate("tasks") }
                HorizontalDivider()
                MoreDestination("校园通知", Icons.Default.Notifications) { showMore = false; onNavigate("notifications") }
                HorizontalDivider()
                MoreDestination("个人中心", Icons.Default.Person) { showMore = false; onNavigate("profile") }
            }
        }
    }
}

@Composable
private fun WorldArea(label: String, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.semantics { contentDescription = "进入$label" }.clickable(role = Role.Button, onClick = onClick))
}

@Composable
private fun WorldIconButton(icon: ImageVector, label: String, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(CircleShape).background(Color(0x88304150))
            .semantics { contentDescription = label }
            .clickable(role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(23.dp))
    }
}

@Composable
private fun WorldDestination(
    label: String,
    icon: ImageVector,
    tint: Color,
    modifier: Modifier = Modifier,
    compact: Boolean = false,
    onClick: () -> Unit,
) {
    Row(
        modifier.shadow(10.dp, CircleShape).clip(CircleShape).background(Color(0xF7FFFEFB))
            .semantics { contentDescription = "进入$label" }
            .clickable(role = Role.Button, onClick = onClick)
            .padding(start = 5.dp, top = 5.dp, end = if (compact) 13.dp else 15.dp, bottom = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(if (compact) 32.dp else 39.dp).clip(CircleShape).background(tint), contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = null, tint = Color.White, modifier = Modifier.size(if (compact) 17.dp else 21.dp))
        }
        Spacer(Modifier.width(if (compact) 7.dp else 10.dp))
        Text(label, color = WorldInk, fontSize = if (compact) 13.sp else 16.sp, fontWeight = FontWeight.Bold)
        if (!compact) {
            Spacer(Modifier.width(7.dp))
            Icon(Icons.Default.ArrowForwardIos, null, tint = Color(0xFF8B929C), modifier = Modifier.size(12.dp))
        }
    }
}

@Composable
private fun MoreDestination(label: String, icon: ImageVector, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(14.dp)).clickable(role = Role.Button, onClick = onClick)
            .padding(vertical = 15.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, null, tint = Color(0xFF677DE3), modifier = Modifier.size(22.dp))
        Spacer(Modifier.width(14.dp))
        Text(label, color = WorldInk, fontSize = 15.sp, fontWeight = FontWeight.Medium, modifier = Modifier.weight(1f))
        Icon(Icons.Default.ArrowForwardIos, null, tint = Color(0xFF8793A2), modifier = Modifier.size(13.dp))
    }
}
