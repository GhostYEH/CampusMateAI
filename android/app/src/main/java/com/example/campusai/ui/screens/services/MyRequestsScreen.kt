package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccessTime
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.Chair
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material.icons.filled.ReceiptLong
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceKind
import com.example.campusai.data.model.ServiceRequest
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.InputBorder
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

/** Shared by the request list and the request-detail timeline. */
fun statusLabel(status: RequestStatus): Pair<String, StatusTone> = when (status) {
    RequestStatus.PENDING -> CampusStrings.Services.STATUS_PENDING to StatusTone.WARNING
    RequestStatus.APPROVED -> CampusStrings.Services.STATUS_APPROVED to StatusTone.SUCCESS
    RequestStatus.REJECTED -> CampusStrings.Services.STATUS_REJECTED to StatusTone.DANGER
    RequestStatus.COMPLETED -> CampusStrings.Services.STATUS_COMPLETED to StatusTone.INFO
}

@Composable
fun MyRequestsScreen(
    repository: ServiceRepository,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
) {
    val requests by repository.requests.collectAsStateWithLifecycle()
    val loading by repository.loading.collectAsStateWithLifecycle()
    val error by repository.error.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    var tab by remember { mutableStateOf("全部") }
    val tabs = listOf("全部", "审核中", "已通过", "已驳回", "已完成")
    val filtered = requests.filter { request ->
        when (tab) {
            "审核中" -> request.status == RequestStatus.PENDING
            "已通过" -> request.status == RequestStatus.APPROVED
            "已驳回" -> request.status == RequestStatus.REJECTED
            "已完成" -> request.status == RequestStatus.COMPLETED
            else -> true
        }
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        Box(Modifier.padding(horizontal = 16.dp)) {
            ServiceHeroHeader("我的申请", "统一查看各类办事申请进度", R.drawable.service_clipboard_hero, onBack, showBack = false)
        }
        LazyRow(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            contentPadding = PaddingValues(vertical = 10.dp),
        ) {
            items(tabs) { item ->
                val active = tab == item
                Box(
                    modifier = Modifier
                        .clip(androidx.compose.foundation.shape.RoundedCornerShape(22.dp))
                        .background(if (active) Primary else Surface)
                        .border(1.dp, if (active) Primary else InputBorder, androidx.compose.foundation.shape.RoundedCornerShape(22.dp))
                        .campusClickable { tab = item }
                        .padding(horizontal = 21.dp, vertical = 11.dp),
                ) { Text(item, color = if (active) Color.White else Muted, fontSize = 14.sp, fontWeight = FontWeight.Bold) }
            }
        }
        when {
            loading -> LoadingState(modifier = Modifier.padding(top = 36.dp))
            error != null -> ErrorState(error.orEmpty(), { scope.launch { repository.refresh() } }, Modifier.padding(top = 30.dp))
            else -> LazyColumn(
                verticalArrangement = Arrangement.spacedBy(16.dp),
                contentPadding = PaddingValues(start = 16.dp, top = 12.dp, end = 16.dp, bottom = BottomDockReservedHeight + 20.dp),
            ) {
                if (filtered.isEmpty()) item { EmptyState(Icons.Default.Assignment, "还没有符合条件的申请") }
                itemsIndexed(filtered, key = { index, request -> "service-request|${request.id}|$index" }) { _, request -> RequestProgressCard(request) { onOpenDetail(request.id) } }
            }
        }
    }
}

@Composable
private fun RequestProgressCard(request: ServiceRequest, onClick: () -> Unit) {
    val (status, statusColor, statusBackground) = when (request.status) {
        RequestStatus.APPROVED -> Triple("已通过", Color(0xFF28B982), Color(0xFFE8F8F1))
        RequestStatus.REJECTED -> Triple("已驳回", Color(0xFFF06045), Color(0xFFFFEEEA))
        RequestStatus.COMPLETED -> Triple("已完成", Color(0xFF526EF2), Color(0xFFEEF0FF))
        RequestStatus.PENDING -> Triple("审核中", Color(0xFFB47A22), Color(0xFFFFF4DA))
    }
    val (icon, iconTint, iconBackground) = when (request.kind) {
        ServiceKind.LEAVE -> Triple(Icons.Default.MedicalServices, Color(0xFF2FBA8C), Color(0xFFEAF8F2))
        ServiceKind.REPAIR -> Triple(Icons.Default.Build, Color(0xFF5C70F3), Color(0xFFEEF0FF))
        ServiceKind.VENUE -> Triple(Icons.Default.Chair, Color(0xFFF09455), Color(0xFFFFF1E8))
        ServiceKind.CERTIFICATE -> Triple(Icons.Default.ReceiptLong, Color(0xFF5C70F3), Color(0xFFEEF0FF))
        ServiceKind.FEEDBACK -> Triple(Icons.Default.Assignment, Color(0xFF5C70F3), Color(0xFFEEF0FF))
    }
    val typeLabel = when (request.kind) {
        ServiceKind.LEAVE -> "请假申请"
        ServiceKind.REPAIR -> "报修申请"
        ServiceKind.VENUE -> "场地申请"
        ServiceKind.CERTIFICATE -> "证明申请"
        ServiceKind.FEEDBACK -> "意见反馈"
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .shadow(10.dp, androidx.compose.foundation.shape.RoundedCornerShape(27.dp), ambientColor = Color(0x103A568D), spotColor = Color(0x103A568D))
            .clip(androidx.compose.foundation.shape.RoundedCornerShape(27.dp))
            .background(Surface)
            .border(1.dp, Color.White.copy(alpha = .7f), androidx.compose.foundation.shape.RoundedCornerShape(27.dp))
            .campusClickable(onClick = onClick)
            .padding(horizontal = 20.dp, vertical = 24.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(76.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(24.dp)).background(iconBackground), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = iconTint, modifier = Modifier.size(37.dp))
        }
        Spacer(Modifier.width(17.dp))
        Column(Modifier.weight(1f)) {
            Text(request.title, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 1)
            Spacer(Modifier.height(8.dp))
            Text(typeLabel, color = Primary, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.clip(androidx.compose.foundation.shape.RoundedCornerShape(8.dp)).background(PrimarySoft).padding(horizontal = 9.dp, vertical = 5.dp))
            Spacer(Modifier.height(12.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.AccessTime, null, tint = Muted, modifier = Modifier.size(16.dp))
                Spacer(Modifier.width(6.dp))
                Text("提交时间  ${request.createdAt}", color = Muted, fontSize = 11.5.sp)
            }
        }
        Column(horizontalAlignment = Alignment.End, verticalArrangement = Arrangement.spacedBy(15.dp)) {
            Text(status, color = statusColor, fontSize = 15.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clip(androidx.compose.foundation.shape.RoundedCornerShape(22.dp)).background(statusBackground).padding(horizontal = 15.dp, vertical = 9.dp))
            Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(21.dp))
        }
    }
}
