package com.example.campusai.ui.screens.users

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

data class UserRow(val name: String, val id: String, val role: String, val status: String)

@Composable
fun UsersScreen(repository: AppRepository) {
    val mockMode by repository.mockMode.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val users = remember { mutableStateListOf(
        UserRow("林知夏", "2024010132", "学生", "正常"),
        UserRow("张明远", "T20180456", "教师", "正常"),
        UserRow("刘文静", "T20170628", "教师", "正常"),
        UserRow("陈一诺", "2024010108", "学生", "正常"),
    ) }
    var showCreateDialog by remember { mutableStateOf(false) }
    var newName by remember { mutableStateOf("") }
    var newId by remember { mutableStateOf("") }

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
                    Text("用户管理", style = MaterialTheme.typography.headlineMedium)
                    Text("集中处理与当前模块相关的校园事务。", color = Muted, fontSize = 13.sp)
                }
                ModeBadge(mockMode)
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Surface)
                    .border(1.dp, Line, RoundedCornerShape(10.dp))
                    .padding(14.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("平台用户", style = MaterialTheme.typography.titleSmall)
                Button(
                    onClick = { showCreateDialog = true },
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Primary),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Icon(Icons.Default.Add, null, modifier = Modifier.size(14.dp))
                    Text("创建用户", fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }

        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(topStart = 10.dp, topEnd = 10.dp))
                    .background(Background)
                    .padding(horizontal = 14.dp, vertical = 10.dp),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Text("姓名", fontWeight = FontWeight.SemiBold, fontSize = 12.sp, color = Muted, modifier = Modifier.weight(1f))
                Text("学号/工号", fontWeight = FontWeight.SemiBold, fontSize = 12.sp, color = Muted, modifier = Modifier.weight(1f))
                Text("角色", fontWeight = FontWeight.SemiBold, fontSize = 12.sp, color = Muted, modifier = Modifier.weight(0.5f))
                Text("状态", fontWeight = FontWeight.SemiBold, fontSize = 12.sp, color = Muted, modifier = Modifier.weight(0.5f))
            }
        }

        itemsIndexed(users) { index, user ->
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Surface)
                    .border(1.dp, Line, RoundedCornerShape(10.dp))
                    .padding(horizontal = 14.dp, vertical = 12.dp)
                    .enterAnimation(delayMs = index * 60, enabled = !reduceMotion),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(user.name, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, modifier = Modifier.weight(1f))
                Text(user.id, fontSize = 13.sp, color = Muted, modifier = Modifier.weight(1f))
                Text(user.role, fontSize = 13.sp, modifier = Modifier.weight(0.5f))
                Text(user.status, fontSize = 13.sp, color = SuccessText, modifier = Modifier.weight(0.5f))
            }
        }
    }

    if (showCreateDialog) {
        AlertDialog(
            onDismissRequest = { showCreateDialog = false },
            title = { Text("创建用户") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedTextField(value = newName, onValueChange = { newName = it }, label = { Text("姓名") }, singleLine = true)
                    OutlinedTextField(value = newId, onValueChange = { newId = it }, label = { Text("学号/工号") }, singleLine = true)
                }
            },
            confirmButton = {
                TextButton(enabled = newName.isNotBlank() && newId.isNotBlank(), onClick = {
                    users.add(UserRow(newName.trim(), newId.trim(), "学生", "待启用"))
                    newName = ""; newId = ""; showCreateDialog = false
                }) { Text("创建") }
            },
            dismissButton = { TextButton(onClick = { showCreateDialog = false }) { Text("取消") } },
        )
    }
}

