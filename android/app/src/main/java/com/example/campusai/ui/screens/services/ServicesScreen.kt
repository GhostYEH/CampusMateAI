package com.example.campusai.ui.screens.services

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CardMembership
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Feedback
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.TaskAlt
import androidx.compose.material.icons.filled.Timer
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceRequest
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private data class ServiceEntry(val title: String, val subtitle: String, val route: String, val icon: ImageVector, val tint: Color)

@Composable
fun ServicesScreen(repository: ServiceRepository, reduceMotion: Boolean, onBack: () -> Unit, onNavigate: (String) -> Unit) {
    val requests by repository.requests.collectAsState()
    val entries = listOf(
        ServiceEntry("请假申请", "在线提交请假申请", "service_leave", Icons.Default.Assignment, Color(0xFF5869F2)),
        ServiceEntry("宿舍报修", "报修维护更快捷", "service_repair", Icons.Default.Build, Color(0xFF45A276)),
        ServiceEntry("证明申请", "各类证明在线开具", "service_form/certificate", Icons.Default.CardMembership, Color(0xFFF08A4D)),
        ServiceEntry("场地申请", "教室场馆一键预约", "service_form/venue", Icons.Default.MeetingRoom, Color(0xFF4F8BF4)),
        ServiceEntry("意见反馈", "反馈建议与问题", "service_form/feedback", Icons.Default.Feedback, Color(0xFF6B61E9)),
        ServiceEntry("我的申请", "查看我的申请记录", "service_mine", Icons.Default.FolderOpen, Color(0xFF35BFA5)),
    )
    val processing = requests.count { it.status == RequestStatus.PENDING }
    val completed = requests.count { it.status == RequestStatus.COMPLETED || it.status == RequestStatus.APPROVED }

    LazyColumn(
        modifier = Modifier.fillMaxWidth().background(Background),
        contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = BottomDockReservedHeight + 18.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item { ServiceHero(onBack) }
        item { ServiceSummary(processing, completed, onNavigate) }
        item { SectionTitle("常用服务", "校园事务，轻松办理", "全部服务") }
        item {
            LazyVerticalGrid(
                columns = GridCells.Fixed(3),
                userScrollEnabled = false,
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
                modifier = Modifier.height(310.dp),
            ) {
                items(entries, key = { it.route }) { entry -> ServiceTile(entry, reduceMotion) { onNavigate(entry.route) } }
            }
        }
        item { SectionTitle("最近申请", "随时掌握办理进度", "全部记录") { onNavigate("service_mine") } }
        item { RecentRequests(requests.take(3), onNavigate) }
    }
}

@Composable private fun ServiceHero(onBack: () -> Unit) {
    androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().height(218.dp)) {
        Image(painterResource(R.drawable.hero_services), null, Modifier.fillMaxWidth().height(218.dp), contentScale = ContentScale.Crop, alpha = .82f)
        Row(Modifier.padding(top = 34.dp), verticalAlignment = Alignment.CenterVertically) {
            CircleIcon(Icons.Default.ChevronRight, "返回", onBack, rotation = 180f)
            Spacer(Modifier.width(16.dp))
            Column {
                Text("办事大厅", color = TextPrimary, fontSize = 31.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(8.dp))
                Text("一站式校园服务中心，办事更轻松", color = Muted, fontSize = 15.sp)
            }
        }
    }
}

@Composable private fun ServiceSummary(processing: Int, completed: Int, onNavigate: (String) -> Unit) {
    Column(Modifier.clip(RoundedCornerShape(25.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(25.dp)).padding(16.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconTile(Icons.Default.Star, Color(0xFF5869F2))
            Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) { Text("高频服务 · 一键直达", color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold); Text("快速处理常用事务，节省您的时间", color = Muted, fontSize = 12.sp) }
            Text("查看全部  ›", color = Muted, fontSize = 12.sp, modifier = Modifier.campusClickable { onNavigate("service_mine") }.padding(8.dp))
        }
        Spacer(Modifier.height(16.dp))
        Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).border(1.dp, Line, RoundedCornerShape(18.dp)).padding(vertical = 18.dp), horizontalArrangement = Arrangement.SpaceEvenly) {
            Metric(Icons.Default.Assignment, processing, "处理中", Primary)
            Metric(Icons.Default.Timer, completed, "已完成", Primary)
            Metric(Icons.Default.TaskAlt, 98, "办结满意度", Success, suffix = "%")
        }
    }
}

@Composable private fun Metric(icon: ImageVector, value: Int, label: String, tint: Color, suffix: String = "") {
    Row(verticalAlignment = Alignment.CenterVertically) { IconTile(icon, tint); Spacer(Modifier.width(9.dp)); Column { Text("$value$suffix", color = TextPrimary, fontSize = 20.sp, fontWeight = FontWeight.Bold); Text(label, color = Muted, fontSize = 11.sp) } }
}
@Composable private fun SectionTitle(title: String, subtitle: String, action: String, onClick: (() -> Unit)? = null) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) { androidx.compose.foundation.layout.Box(Modifier.size(width = 5.dp, height = 25.dp).clip(CircleShape).background(Primary)); Spacer(Modifier.width(10.dp)); Text(title, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.width(12.dp)); Text(subtitle, color = Muted, fontSize = 11.sp, modifier = Modifier.weight(1f)); Text("$action  ›", color = Muted, fontSize = 12.sp, modifier = Modifier.campusClickable { onClick?.invoke() }.padding(4.dp)) }
}
@Composable private fun ServiceTile(entry: ServiceEntry, reduceMotion: Boolean, onClick: () -> Unit) {
    Column(Modifier.clip(RoundedCornerShape(20.dp)).background(Surface).campusClickable(onClick = onClick).enterAnimation(enabled = !reduceMotion).padding(vertical = 16.dp, horizontal = 7.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) { IconTile(entry.icon, entry.tint); Spacer(Modifier.height(12.dp)); Text(entry.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(5.dp)); Text(entry.subtitle, color = Muted, fontSize = 10.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }
}
@Composable private fun RecentRequests(items: List<ServiceRequest>, onNavigate: (String) -> Unit) {
    Column(Modifier.clip(RoundedCornerShape(20.dp)).background(Surface).padding(horizontal = 16.dp, vertical = 7.dp)) { items.forEachIndexed { index, request -> RecentRequest(request, onNavigate); if (index < items.lastIndex) androidx.compose.foundation.layout.Box(Modifier.fillMaxWidth().height(1.dp).background(Line)) }; Text("更多申请记录⌄", color = Muted, fontSize = 13.sp, modifier = Modifier.fillMaxWidth().campusClickable { onNavigate("service_mine") }.padding(14.dp), textAlign = androidx.compose.ui.text.style.TextAlign.Center) }
}
@Composable private fun RecentRequest(request: ServiceRequest, onNavigate: (String) -> Unit) {
    val (icon, tint) = when (request.kind) { com.example.campusai.data.model.ServiceKind.REPAIR -> Icons.Default.Build to Color(0xFF45A276); com.example.campusai.data.model.ServiceKind.CERTIFICATE -> Icons.Default.CardMembership to Color(0xFFF08A4D); else -> Icons.Default.Assignment to Primary }
    val done = request.status != RequestStatus.PENDING
    Row(Modifier.fillMaxWidth().campusClickable { onNavigate("service_detail/${request.id}") }.padding(vertical = 11.dp), verticalAlignment = Alignment.CenterVertically) { IconTile(icon, tint); Spacer(Modifier.width(12.dp)); Column(Modifier.weight(1f)) { Text(request.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis); Text("申请时间：${request.createdAt}", color = Muted, fontSize = 10.5.sp) }; Text(if (done) "已完成" else "处理中", color = if (done) Success else Primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold); Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(17.dp)) }
}
@Composable private fun IconTile(icon: ImageVector, tint: Color) { androidx.compose.foundation.layout.Box(Modifier.size(48.dp).clip(RoundedCornerShape(15.dp)).background(tint.copy(alpha = .12f)), contentAlignment = Alignment.Center) { Icon(icon, null, tint = tint, modifier = Modifier.size(25.dp)) } }
@Composable private fun CircleIcon(icon: ImageVector, label: String, onClick: () -> Unit, rotation: Float = 0f) { androidx.compose.foundation.layout.Box(Modifier.size(48.dp).clip(CircleShape).background(Surface).border(1.dp, Line, CircleShape).campusClickable(onClick = onClick), contentAlignment = Alignment.Center) { Icon(icon, label, tint = TextPrimary, modifier = Modifier.size(26.dp).rotate(rotation)) } }
