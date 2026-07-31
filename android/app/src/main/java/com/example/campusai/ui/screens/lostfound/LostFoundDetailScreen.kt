package com.example.campusai.ui.screens.lostfound

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Inventory2
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.model.LostFoundStatus
import com.example.campusai.data.repository.LostFoundRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusPrimaryButton
import com.example.campusai.ui.components.ConfirmDialog
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.DangerText
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

@Composable
fun LostFoundDetailScreen(
    itemId: Long,
    repository: LostFoundRepository,
    onBack: () -> Unit,
) {
    val items by repository.items.collectAsState()
    val item = items.find { it.id == itemId }
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboardManager.current
    var showDeleteConfirm by remember { mutableStateOf(false) }
    var contactCopied by remember { mutableStateOf(false) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp)
            .verticalScroll(rememberScrollState()),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(title = CampusStrings.LostFound.DETAIL_TITLE, onBack = onBack)
        Spacer(Modifier.height(14.dp))

        if (item == null) {
            EmptyState(Icons.Default.Inventory2, CampusStrings.LostFound.EMPTY)
        } else {
            val (statusLabel, statusTone) = lostFoundStatusTag(item)
            CampusCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        item.title,
                        color = TextPrimary,
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.weight(1f),
                    )
                    StatusTag(statusLabel, statusTone)
                }
                Spacer(Modifier.height(8.dp))
                Row {
                    StatusTag(
                        if (item.kind == LostFoundKind.LOST) CampusStrings.LostFound.KIND_LOST else CampusStrings.LostFound.KIND_FOUND,
                        if (item.kind == LostFoundKind.LOST) StatusTone.DANGER else StatusTone.SUCCESS,
                    )
                    Spacer(Modifier.width(6.dp))
                    StatusTag(item.category, StatusTone.NEUTRAL)
                }
                Spacer(Modifier.height(12.dp))
                ItemThumbnail(item.imageUri, size = 120.dp)
                Spacer(Modifier.height(12.dp))
                DetailInfoRow(CampusStrings.LostFound.FIELD_TIME, item.time)
                DetailInfoRow(CampusStrings.LostFound.FIELD_LOCATION, item.location)
                DetailInfoRow("发布者", item.publisher)
                Spacer(Modifier.height(8.dp))
                Text(item.description, color = TextPrimary, fontSize = 13.sp, lineHeight = 20.sp)
            }
            Spacer(Modifier.height(12.dp))
            CampusCard {
                if (item.anonymous) {
                    Text(CampusStrings.LostFound.CONTACT_ANONYMOUS, color = Muted, fontSize = 12.5.sp)
                } else {
                    Text(CampusStrings.LostFound.FIELD_CONTACT, color = Muted, fontSize = 11.5.sp)
                    Spacer(Modifier.height(4.dp))
                    Text(item.contact, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                }
            }
            Spacer(Modifier.height(18.dp))
            if (!item.anonymous) {
                CampusPrimaryButton(
                    text = if (contactCopied) CampusStrings.LostFound.CONTACT_COPIED else CampusStrings.LostFound.CONTACT,
                    onClick = {
                        clipboard.setText(AnnotatedString(item.contact))
                        contactCopied = true
                    },
                )
                Spacer(Modifier.height(10.dp))
            }
            if (item.mine && item.status == LostFoundStatus.OPEN) {
                CampusPrimaryButton(
                    text = if (item.kind == LostFoundKind.LOST) CampusStrings.LostFound.MARK_CLOSED_LOST else CampusStrings.LostFound.MARK_CLOSED_FOUND,
                    onClick = { scope.launch { repository.close(item.id) } },
                )
                Spacer(Modifier.height(10.dp))
            }
            if (item.mine) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(46.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(DangerText.copy(alpha = .1f))
                        .campusClickable { showDeleteConfirm = true },
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Spacer(Modifier.weight(1f))
                    Text(CampusStrings.Common.DELETE, color = DangerText, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                    Spacer(Modifier.weight(1f))
                }
            }
            Spacer(Modifier.height(120.dp))
        }
    }

    if (showDeleteConfirm && item != null) {
        ConfirmDialog(
            title = CampusStrings.LostFound.DELETE_TITLE,
            message = CampusStrings.LostFound.DELETE_MESSAGE,
            confirmText = CampusStrings.Common.DELETE,
            danger = true,
            onConfirm = {
                showDeleteConfirm = false
                scope.launch {
                    repository.delete(item.id)
                    onBack()
                }
            },
            onDismiss = { showDeleteConfirm = false },
        )
    }
}

@Composable
private fun DetailInfoRow(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
    ) {
        Text(label, color = Muted, fontSize = 12.sp, modifier = Modifier.width(56.dp))
        Text(value, color = TextPrimary, fontSize = 13.sp)
    }
}
