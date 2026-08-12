package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.BugReport
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.HelpOutline
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight

@Composable
fun HelpFeedbackScreen(
    repository: AppRepository,
    onSubmitFeedback: () -> Unit,
) {
    val backendOnline by repository.backendOnline.collectAsState()

    Box(Modifier.fillMaxSize().background(ReferencePageBackground)) {
        LazyColumn(
            contentPadding = PaddingValues(start = 16.dp, top = 18.dp, end = 16.dp, bottom = BottomDockReservedHeight + 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            /*
            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(ReferenceSurface)
                            .campusClickable(onClick = onBack),
                        contentAlignment = Alignment.Center,
                    ) { Icon(Icons.Default.ArrowBack, "返回", tint = ReferenceText) }
                    Column(Modifier.padding(start = 12.dp)) {
                        Text("帮助与反馈", color = ReferenceText, fontSize = 23.sp, fontWeight = FontWeight.Bold)
                        Text("遇到问题时，从这里获得明确的下一步", color = ReferenceMuted, fontSize = 12.sp)
                    }
                }
            }
            */
            item {
                val online = backendOnline
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp))
                        .background(if (online) Color(0xFFEAF8F0) else Color(0xFFFFEFEA))
                        .padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(if (online) Icons.Default.CloudDone else Icons.Default.BugReport, null,
                        tint = if (online) Color(0xFF17A66A) else Color(0xFFF0784A))
                    Column(Modifier.padding(start = 12.dp).weight(1f)) {
                        Text(if (online) "服务连接正常" else "正在重新连接服务", color = ReferenceText, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                        Text(if (online) "当前功能可以使用真实后端数据。" else "请稍候，或检查此设备的后端地址与网络。", color = ReferenceMuted, fontSize = 11.sp)
                    }
                }
            }
            item {
                HelpActionCard(
                    icon = Icons.Default.Send,
                    title = "提交问题与建议",
                    detail = "功能异常、体验建议或需要协助的校园事务",
                    accent = ReferencePrimary,
                    onClick = onSubmitFeedback,
                )
            }
            item { Text("常见问题", color = ReferenceText, fontSize = 15.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp, start = 4.dp)) }
            item { HelpActionCard(Icons.Default.HelpOutline, "为什么会显示未连接？", "登录后应用会自动检查服务；真机调试需使用电脑的局域网 IP，而不是 10.0.2.2。", ReferencePrimary, onClick = {}) }
            item { HelpActionCard(Icons.Default.HelpOutline, "如何重新检查连接？", "进入设置页即可刷新服务状态；连接恢复后无需重新登录。", ReferencePrimary, onClick = {}) }
        }
    }
}

@Composable
private fun HelpActionCard(
    icon: ImageVector,
    title: String,
    detail: String,
    accent: Color,
    onClick: () -> Unit,
) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(20.dp)).background(ReferenceSurface)
            .clickable(onClick = onClick).padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(42.dp).clip(RoundedCornerShape(14.dp)).background(ReferencePrimarySoft), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = accent, modifier = Modifier.size(21.dp))
        }
        Column(Modifier.padding(start = 12.dp).weight(1f)) {
            Text(title, color = ReferenceText, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text(detail, color = ReferenceMuted, fontSize = 11.sp, lineHeight = 16.sp)
        }
        Icon(Icons.Default.ChevronRight, null, tint = ReferenceMuted)
    }
}
