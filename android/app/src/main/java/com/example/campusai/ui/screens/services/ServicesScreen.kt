package com.example.campusai.ui.screens.services

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.model.ServiceRequest
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Success
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private val PageHorizontalPadding = 24.dp
private val SectionSpacing = 15.dp
private val HeroHeight = 210.dp
private val LargeCardRadius = 26.dp
private val ServiceCardRadius = 22.dp
private val IconBoxSize = 48.dp
private val ServiceCardHeight = 118.dp

private val HeroTitle = Color(0xFF112957)
private val HeroSubtitle = Color(0xFF62749A)
private val Blue = Color(0xFF4F86EE)
private val Purple = Color(0xFF6B5CF0)
private val Green = Color(0xFF36B98E)

private data class ServiceEntry(
    val title: String,
    val subtitle: String,
    val route: String,
    val icon: ImageVector,
    val tint: Color,
)

@Composable
fun ServicesScreen(
    repository: ServiceRepository,
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onNavigate: (String) -> Unit,
) {
    val requests by repository.requests.collectAsStateWithLifecycle()
    val entries = listOf(
        ServiceEntry("请假申请", "在线提交请假申请", "service_leave", Icons.Default.Assignment, Color(0xFF6658EC)),
        ServiceEntry("宿舍报修", "报修维护更快捷", "service_repair", Icons.Default.Build, Color(0xFF45AF85)),
        ServiceEntry("证明申请", "各类证明在线开具", "service_form/certificate", Icons.Default.CardMembership, Color(0xFFF28B53)),
        ServiceEntry("场地申请", "场地预约与申请", "service_form/venue", Icons.Default.MeetingRoom, Color(0xFF4E86E9)),
        ServiceEntry("意见反馈", "反馈问题与建议", "service_form/feedback", Icons.Default.Feedback, Color(0xFF7662EA)),
        ServiceEntry("我的申请", "查看申请进度", "service_mine", Icons.Default.FolderOpen, Color(0xFF34B8AD)),
    )
    val processing = requests.count { it.status == RequestStatus.PENDING }
    val completed = requests.count {
        it.status == RequestStatus.COMPLETED || it.status == RequestStatus.APPROVED
    }

    LazyColumn(
        modifier = Modifier.fillMaxWidth().background(Background),
        contentPadding = PaddingValues(
            start = PageHorizontalPadding,
            end = PageHorizontalPadding,
            bottom = BottomDockReservedHeight + 20.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(SectionSpacing),
    ) {
        item { ServiceHallHero() }
        item { QuickServiceSummaryCard(processing, completed, onNavigate) }
        item {
            SectionTitle(
                title = "常用服务",
                subtitle = "校园事务，轻松办理",
                action = "全部服务",
                onClick = { onNavigate("service_mine") },
            )
        }
        item { CommonServicesSection(entries, reduceMotion, onNavigate) }
        item {
            SectionTitle(
                title = "最近申请",
                subtitle = "随时掌握办理进度",
                action = "全部记录",
                onClick = { onNavigate("service_mine") },
            )
        }
        if (requests.isNotEmpty()) {
            item { RecentRequestsSection(requests.take(3), onNavigate) }
        }
    }
}

@Composable
private fun ServiceHallHero() {
    Box(Modifier.fillMaxWidth().height(HeroHeight)) {
        Image(
            painter = painterResource(R.drawable.hero_services),
            contentDescription = null,
            modifier = Modifier.fillMaxWidth().height(HeroHeight),
            contentScale = ContentScale.Crop,
            alpha = .82f,
        )
        Box(
            Modifier
                .fillMaxWidth()
                .height(HeroHeight)
                .background(
                    Brush.horizontalGradient(
                        0f to Background.copy(alpha = .44f),
                        .38f to Background.copy(alpha = .15f),
                        .72f to Color.Transparent,
                        1f to Background.copy(alpha = .12f),
                    ),
                ),
        )
        Box(
            Modifier
                .fillMaxWidth()
                .height(HeroHeight)
                .background(
                    Brush.verticalGradient(
                        0f to Background.copy(alpha = .62f),
                        .12f to Color.Transparent,
                        .82f to Color.Transparent,
                        1f to Background.copy(alpha = .58f),
                    ),
                ),
        )
        Column(
            modifier = Modifier
                .align(Alignment.CenterStart)
                .padding(start = 4.dp, bottom = 4.dp),
        ) {
            Text(
                text = "办事大厅",
                color = HeroTitle,
                fontSize = 33.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = .2.sp,
            )
            Spacer(Modifier.height(9.dp))
            Text(
                text = "一站式校园服务中心，办事更轻松",
                color = HeroSubtitle,
                fontSize = 13.5.sp,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                modifier = Modifier.fillMaxWidth(.82f),
            )
        }
    }
}

@Composable
private fun QuickServiceSummaryCard(
    processing: Int,
    completed: Int,
    onNavigate: (String) -> Unit,
) {
    val shape = RoundedCornerShape(LargeCardRadius)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(7.dp, shape, ambientColor = Primary.copy(alpha = .07f), spotColor = Primary.copy(alpha = .08f))
            .clip(shape)
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .82f), shape)
            .padding(16.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconTile(Icons.Default.Star, Purple, size = 46.dp, iconSize = 24.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "高频服务，一键直达",
                    color = TextPrimary,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                )
                Spacer(Modifier.height(3.dp))
                Text("快速处理常用事务，节省您的时间", color = Muted, fontSize = 11.5.sp)
            }
            ActionLink("查看全部", onClick = { onNavigate("service_mine") })
        }
        Spacer(Modifier.height(15.dp))
        ServiceStatsRow(processing, completed)
    }
}

@Composable
private fun ServiceStatsRow(processing: Int, completed: Int) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(19.dp))
            .border(1.dp, Line.copy(alpha = .76f), RoundedCornerShape(19.dp))
            .padding(7.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
    ) {
        Metric(Icons.Default.Assignment, processing, "处理中", Purple)
        Metric(Icons.Default.Timer, completed, "已完成", Blue)
        Metric(Icons.Default.TaskAlt, 98, "办结满意度", Green, suffix = "%")
    }
}

@Composable
private fun RowScope.Metric(
    icon: ImageVector,
    value: Int,
    label: String,
    tint: Color,
    suffix: String = "",
) {
    Row(
        modifier = Modifier
            .weight(1f)
            .height(67.dp)
            .clip(RoundedCornerShape(15.dp))
            .background(tint.copy(alpha = .065f))
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconTile(icon, tint, size = 39.dp, iconSize = 21.dp)
        Spacer(Modifier.width(6.dp))
        Column {
            Text(
                "$value$suffix",
                color = TextPrimary,
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
            )
            Text(label, color = Muted, fontSize = 9.sp, maxLines = 1)
        }
    }
}

@Composable
private fun SectionTitle(
    title: String,
    subtitle: String,
    action: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth().height(31.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(width = 5.dp, height = 23.dp)
                .clip(CircleShape)
                .background(Primary),
        )
        Spacer(Modifier.width(10.dp))
        Text(title, color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.width(10.dp))
        Text(
            subtitle,
            color = Muted,
            fontSize = 10.5.sp,
            modifier = Modifier.weight(1f),
            maxLines = 1,
        )
        ActionLink(action, onClick)
    }
}

@Composable
private fun ActionLink(text: String, onClick: () -> Unit) {
    Row(
        modifier = Modifier.campusClickable(onClick = onClick).padding(start = 5.dp, top = 6.dp, bottom = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text, color = HeroSubtitle, fontSize = 11.5.sp, maxLines = 1)
        Spacer(Modifier.width(3.dp))
        Icon(Icons.Default.ChevronRight, null, tint = HeroSubtitle.copy(alpha = .72f), modifier = Modifier.size(16.dp))
    }
}

@Composable
private fun CommonServicesSection(
    entries: List<ServiceEntry>,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        entries.chunked(3).forEach { rowEntries ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                rowEntries.forEach { entry ->
                    ServiceShortcutCard(
                        entry = entry,
                        reduceMotion = reduceMotion,
                        onClick = { onNavigate(entry.route) },
                    )
                }
            }
        }
    }
}

@Composable
private fun RowScope.ServiceShortcutCard(
    entry: ServiceEntry,
    reduceMotion: Boolean,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(ServiceCardRadius)
    Column(
        modifier = Modifier
            .weight(1f)
            .height(ServiceCardHeight)
            .shadow(5.dp, shape, ambientColor = Primary.copy(alpha = .045f), spotColor = Primary.copy(alpha = .06f))
            .clip(shape)
            .background(Surface)
            .border(1.dp, Color.White.copy(alpha = .94f), shape)
            .campusClickable(onClick = onClick)
            .enterAnimation(enabled = !reduceMotion)
            .padding(horizontal = 6.dp, vertical = 10.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        IconTile(entry.icon, entry.tint)
        Spacer(Modifier.height(8.dp))
        Text(
            entry.title,
            color = TextPrimary,
            fontSize = 13.5.sp,
            fontWeight = FontWeight.Bold,
            maxLines = 1,
        )
        Spacer(Modifier.height(3.dp))
        Text(
            entry.subtitle,
            color = Muted,
            fontSize = 9.5.sp,
            lineHeight = 12.sp,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
private fun RecentRequestsSection(items: List<ServiceRequest>, onNavigate: (String) -> Unit) {
    val shape = RoundedCornerShape(ServiceCardRadius)
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(5.dp, shape, ambientColor = Primary.copy(alpha = .04f), spotColor = Primary.copy(alpha = .05f))
            .clip(shape)
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .65f), shape)
            .padding(horizontal = 16.dp, vertical = 7.dp),
    ) {
        items.forEachIndexed { index, request ->
            RecentRequest(request, onNavigate)
            if (index < items.lastIndex) {
                Box(Modifier.fillMaxWidth().height(1.dp).background(Line.copy(alpha = .7f)))
            }
        }
    }
}

@Composable
private fun RecentRequest(request: ServiceRequest, onNavigate: (String) -> Unit) {
    val (icon, tint) = when (request.kind) {
        ServiceKind.REPAIR -> Icons.Default.Build to Color(0xFF45AF85)
        ServiceKind.CERTIFICATE -> Icons.Default.CardMembership to Color(0xFFF28B53)
        else -> Icons.Default.Assignment to Purple
    }
    val done = request.status != RequestStatus.PENDING
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .campusClickable { onNavigate("service_detail/${request.id}") }
            .padding(vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconTile(icon, tint, size = 43.dp, iconSize = 23.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(
                request.title,
                color = TextPrimary,
                fontSize = 13.5.sp,
                fontWeight = FontWeight.Bold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Spacer(Modifier.height(2.dp))
            Text("申请时间：${request.createdAt}", color = Muted, fontSize = 10.sp)
        }
        Text(
            if (done) "已完成" else "处理中",
            color = if (done) Success else Primary,
            fontSize = 10.5.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Icon(Icons.Default.ChevronRight, null, tint = Muted.copy(alpha = .7f), modifier = Modifier.size(17.dp))
    }
}

@Composable
private fun IconTile(
    icon: ImageVector,
    tint: Color,
    size: androidx.compose.ui.unit.Dp = IconBoxSize,
    iconSize: androidx.compose.ui.unit.Dp = 25.dp,
) {
    Box(
        modifier = Modifier
            .size(size)
            .shadow(4.dp, RoundedCornerShape(16.dp), ambientColor = tint.copy(alpha = .08f), spotColor = tint.copy(alpha = .1f))
            .clip(RoundedCornerShape(16.dp))
            .background(tint.copy(alpha = .105f))
            .border(1.dp, Color.White.copy(alpha = .7f), RoundedCornerShape(16.dp)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, null, tint = tint, modifier = Modifier.size(iconSize))
    }
}
