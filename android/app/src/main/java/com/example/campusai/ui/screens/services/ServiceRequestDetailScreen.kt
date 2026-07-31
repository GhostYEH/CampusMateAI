package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.repository.ServiceRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.TextPrimary

@Composable
fun ServiceRequestDetailScreen(
    requestId: Long,
    repository: ServiceRepository,
    onBack: () -> Unit,
) {
    val requests by repository.requests.collectAsState()
    val request = requests.find { it.id == requestId }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.Services.DETAIL_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))

        if (request == null) {
            EmptyState(Icons.Default.Assignment, CampusStrings.Services.EMPTY)
        } else {
            val (label, tone) = statusLabel(request.status)
            CampusCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        request.title,
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    StatusTag(label, tone)
                }
                Spacer(Modifier.height(6.dp))
                Text(
                    "${CampusStrings.Services.SUBMITTED_AT} ${request.createdAt}",
                    color = Muted,
                    fontSize = 11.5.sp,
                )
                Spacer(Modifier.height(12.dp))
                request.fields.forEach { (fieldLabel, value) ->
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(vertical = 6.dp),
                    ) {
                        Text(fieldLabel, color = Muted, fontSize = 12.sp, modifier = Modifier.width(72.dp))
                        Text(value, color = TextPrimary, fontSize = 13.sp, modifier = Modifier.weight(1f))
                    }
                }
                if (request.attachmentUris.isNotEmpty()) {
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "附件 ${request.attachmentUris.size} 个（本地记录）",
                        color = Muted,
                        fontSize = 11.5.sp,
                    )
                }
            }
            Spacer(Modifier.height(12.dp))
            CampusCard {
                Text(CampusStrings.Services.TIMELINE, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.height(12.dp))
                request.timeline.forEachIndexed { index, event ->
                    val last = index == request.timeline.lastIndex
                    Row {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(
                                Modifier
                                    .size(10.dp)
                                    .clip(CircleShape)
                                    .background(if (index == 0) Primary else Line)
                                    .border(1.5.dp, Primary, CircleShape),
                            )
                            if (!last) {
                                Box(Modifier.width(1.5.dp).height(46.dp).background(Line))
                            }
                        }
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.padding(bottom = 14.dp)) {
                            Text(event.title, color = TextPrimary, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.height(2.dp))
                            Text(event.detail, color = Muted, fontSize = 11.5.sp)
                            Spacer(Modifier.height(2.dp))
                            Text(event.time, color = Muted, fontSize = 10.5.sp)
                        }
                    }
                }
            }
            Spacer(Modifier.height(120.dp))
        }
    }
}
