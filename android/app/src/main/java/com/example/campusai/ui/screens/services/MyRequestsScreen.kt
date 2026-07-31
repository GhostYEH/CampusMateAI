package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.RequestStatus
import com.example.campusai.data.model.ServiceRequest
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

/** 状态 -> 标签文案与色调（统一使用设计系统中的 StatusTag）。 */
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
    val requests by repository.requests.collectAsState()
    val loading by repository.loading.collectAsState()
    val error by repository.error.collectAsState()
    val scope = rememberCoroutineScope()
    var tab by remember { mutableStateOf(CampusStrings.Services.TAB_ALL) }

    val tabs = listOf(
        CampusStrings.Services.TAB_ALL,
        CampusStrings.Services.TAB_PENDING,
        CampusStrings.Services.TAB_APPROVED,
        CampusStrings.Services.TAB_REJECTED,
        CampusStrings.Services.TAB_COMPLETED,
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.Services.MINE_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))
        FilterChipRow(options = tabs, selected = tab, onSelect = { tab = it })
        Spacer(Modifier.height(12.dp))

        when {
            loading -> LoadingState()
            error != null -> ErrorState(
                message = error.orEmpty(),
                onRetry = { scope.launch { repository.refresh() } },
            )
            else -> {
                val filtered = requests.filter { request ->
                    when (tab) {
                        CampusStrings.Services.TAB_PENDING -> request.status == RequestStatus.PENDING
                        CampusStrings.Services.TAB_APPROVED -> request.status == RequestStatus.APPROVED
                        CampusStrings.Services.TAB_REJECTED -> request.status == RequestStatus.REJECTED
                        CampusStrings.Services.TAB_COMPLETED -> request.status == RequestStatus.COMPLETED
                        else -> true
                    }
                }
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    contentPadding = PaddingValues(
                        bottom = WindowInsets.navigationBars.asPaddingValues()
                            .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
                    ),
                ) {
                    if (filtered.isEmpty()) {
                        item { EmptyState(Icons.Default.Assignment, CampusStrings.Services.EMPTY) }
                    } else {
                        items(filtered, key = { it.id }) { request ->
                            RequestRow(request, onClick = { onOpenDetail(request.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun RequestRow(request: ServiceRequest, onClick: () -> Unit) {
    val (label, tone) = statusLabel(request.status)
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onClick),
        padding = PaddingValues(14.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(request.title, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(5.dp))
                Text(
                    "${CampusStrings.Services.SUBMITTED_AT} ${request.createdAt}",
                    color = Muted,
                    fontSize = 11.5.sp,
                )
            }
            StatusTag(label, tone)
        }
    }
}
