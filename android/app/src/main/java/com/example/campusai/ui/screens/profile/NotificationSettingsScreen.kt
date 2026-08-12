package com.example.campusai.ui.screens.profile

import android.content.Intent
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationManagerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.platform.LocalLifecycleOwner
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Danger
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

@Composable
fun NotificationSettingsScreen(
    repository: AppRepository,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val monitoredGroups by repository.getMonitoredGroupChats().collectAsState(initial = emptySet())
    val wecomGroups by repository.getWecomGroupChats().collectAsState(initial = emptySet())
    val qqGroups by repository.getQqGroupChats().collectAsState(initial = emptySet())
    var newGroup by remember { mutableStateOf("") }
    var newWecomGroup by remember { mutableStateOf("") }
    var newQqGroup by remember { mutableStateOf("") }
    var isNotificationListenerEnabled by remember { mutableStateOf(false) }

    fun checkNotificationListener() {
        val enabledPackages = NotificationManagerCompat.getEnabledListenerPackages(context)
        isNotificationListenerEnabled = enabledPackages.contains(context.packageName)
    }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                checkNotificationListener()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
        }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background),
        contentPadding = PaddingValues(
            start = 20.dp,
            end = 20.dp,
            top = 12.dp,
            bottom = BottomDockReservedHeight + 24.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            NotificationStatusRow(
                granted = isNotificationListenerEnabled,
                onOpenSettings = {
                    val intent = Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)
                    context.startActivity(intent)
                },
                modifier = Modifier.enterAnimation(enabled = !reduceMotion),
            )
        }
        item {
            WhitelistSection(
                title = "微信群聊",
                groups = monitoredGroups.toList(),
                onRemove = { group ->
                    scope.launch { repository.removeMonitoredGroupChat(group) }
                },
                modifier = Modifier.enterAnimation(delayMs = 70, enabled = !reduceMotion),
            )
        }
        item {
            AddGroupBar(
                value = newGroup,
                onValueChange = { newGroup = it },
                onAdd = {
                    if (newGroup.isNotBlank()) {
                        scope.launch {
                            repository.addMonitoredGroupChat(newGroup.trim())
                            newGroup = ""
                        }
                    }
                },
                label = "新增微信群名称",
            )
        }
        item {
            WhitelistSection(
                title = "企业微信群聊",
                groups = wecomGroups.toList(),
                onRemove = { group ->
                    scope.launch { repository.removeWecomGroupChat(group) }
                },
                modifier = Modifier.enterAnimation(delayMs = 100, enabled = !reduceMotion),
            )
        }
        item {
            AddGroupBar(
                value = newWecomGroup,
                onValueChange = { newWecomGroup = it },
                onAdd = {
                    if (newWecomGroup.isNotBlank()) {
                        scope.launch {
                            repository.addWecomGroupChat(newWecomGroup.trim())
                            newWecomGroup = ""
                        }
                    }
                },
                label = "新增企业微信群名称",
            )
        }
        item {
            WhitelistSection(
                title = "QQ 群聊",
                groups = qqGroups.toList(),
                onRemove = { group ->
                    scope.launch { repository.removeQqGroupChat(group) }
                },
                modifier = Modifier.enterAnimation(delayMs = 130, enabled = !reduceMotion),
            )
        }
        item {
            AddGroupBar(
                value = newQqGroup,
                onValueChange = { newQqGroup = it },
                onAdd = {
                    if (newQqGroup.isNotBlank()) {
                        scope.launch {
                            repository.addQqGroupChat(newQqGroup.trim())
                            newQqGroup = ""
                        }
                    }
                },
                label = "新增 QQ 群名称",
            )
        }
    }
}

@Composable
private fun NotificationStatusRow(
    granted: Boolean,
    onOpenSettings: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(Surface)
            .padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(32.dp).clip(RoundedCornerShape(10.dp))
                .background(if (granted) PrimarySoft else Danger.copy(alpha = .1f)),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                Icons.Default.Chat,
                null,
                tint = if (granted) Primary else Danger,
                modifier = Modifier.size(16.dp),
            )
        }
        Spacer(Modifier.width(10.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                "通知访问权限",
                fontSize = 13.sp,
                fontWeight = FontWeight.Medium,
                color = TextPrimary,
            )
            Text(
                if (granted) "已授权" else "未开启，开启后才能捕获微信/企业微信通知",
                color = Muted,
                fontSize = 11.sp,
            )
        }
        if (!granted) {
            TextButton(
                onClick = onOpenSettings,
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
            ) {
                Text("去开启", fontSize = 12.sp, color = Primary)
            }
        } else {
            Text("已授权", color = Primary, fontSize = 12.sp, fontWeight = FontWeight.Medium)
        }
    }
}

@Composable
private fun WhitelistSection(
    title: String,
    groups: List<String>,
    onRemove: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Column(modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(start = 2.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                title,
                color = TextPrimary,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.weight(1f),
            )
            Text(
                "${groups.size} 个",
                color = Muted,
                fontSize = 12.sp,
            )
        }
        Column(
            Modifier.fillMaxWidth()
                .clip(RoundedCornerShape(14.dp))
                .background(Surface)
                .padding(horizontal = 14.dp),
        ) {
            if (groups.isEmpty()) {
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center,
                ) {
                    Icon(Icons.Default.Chat, null, tint = Muted, modifier = Modifier.size(14.dp))
                    Spacer(Modifier.width(6.dp))
                    Text("尚未添加群聊", color = Muted, fontSize = 12.sp)
                }
            } else {
                groups.forEachIndexed { index, group ->
                    Row(
                        Modifier.fillMaxWidth().padding(vertical = 11.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Icon(
                            Icons.Default.Chat,
                            null,
                            tint = Primary,
                            modifier = Modifier.size(16.dp),
                        )
                        Text(
                            group,
                            color = TextPrimary,
                            fontSize = 13.sp,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier.padding(start = 10.dp).weight(1f),
                        )
                        Icon(
                            Icons.Default.Delete,
                            "移除",
                            tint = Muted,
                            modifier = Modifier
                                .size(28.dp)
                                .clip(RoundedCornerShape(8.dp))
                                .campusClickable(onClick = { onRemove(group) })
                                .padding(6.dp),
                        )
                    }
                    if (index != groups.lastIndex) {
                        HorizontalDivider(color = Line)
                    }
                }
            }
        }
    }
}

@Composable
private fun AddGroupBar(
    value: String,
    onValueChange: (String) -> Unit,
    onAdd: () -> Unit,
    label: String = "新增群聊名称",
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            value = value,
            onValueChange = onValueChange,
            label = { Text(label) },
            modifier = Modifier.weight(1f),
            singleLine = true,
            shape = RoundedCornerShape(10.dp),
        )
        Spacer(Modifier.width(10.dp))
        Button(
            onClick = onAdd,
            enabled = value.isNotBlank(),
            shape = RoundedCornerShape(10.dp),
            modifier = Modifier.size(46.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Primary,
                disabledContainerColor = Primary.copy(alpha = 0.3f),
            ),
            contentPadding = PaddingValues(0.dp),
        ) {
            Icon(Icons.Default.Add, null, modifier = Modifier.size(18.dp))
        }
    }
}
