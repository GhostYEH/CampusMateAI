package com.example.campusai.ui.screens.lostfound

import android.annotation.SuppressLint
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.LostFoundItem
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.model.LostFoundStatus
import com.example.campusai.data.repository.LocalLostFoundRepository
import com.example.campusai.data.repository.LostFoundRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.CampusTextField
import com.example.campusai.ui.components.EmptyState
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.FormDropdown
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.StatusTag
import com.example.campusai.ui.components.StatusTone
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** 状态标签（列表 / 详情共用）。 */
fun lostFoundStatusTag(item: LostFoundItem): Pair<String, StatusTone> = when {
    item.status == LostFoundStatus.CLOSED && item.kind == LostFoundKind.LOST ->
        CampusStrings.LostFound.STATUS_CLOSED_LOST to StatusTone.NEUTRAL
    item.status == LostFoundStatus.CLOSED ->
        CampusStrings.LostFound.STATUS_CLOSED_FOUND to StatusTone.NEUTRAL
    item.kind == LostFoundKind.LOST ->
        CampusStrings.LostFound.STATUS_OPEN_LOST to StatusTone.WARNING
    else ->
        CampusStrings.LostFound.STATUS_OPEN_FOUND to StatusTone.INFO
}

@Composable
fun LostFoundScreen(
    repository: LostFoundRepository,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
    onOpenPublish: () -> Unit,
    onOpenMine: () -> Unit,
) {
    val items by repository.items.collectAsState()
    val loading by repository.loading.collectAsState()
    val error by repository.error.collectAsState()
    val scope = rememberCoroutineScope()

    var tab by remember { mutableStateOf(CampusStrings.LostFound.TAB_LOST) }
    var keyword by remember { mutableStateOf("") }
    var category by remember { mutableStateOf(CampusStrings.LostFound.CATEGORY_ALL) }
    var location by remember { mutableStateOf(CampusStrings.LostFound.CATEGORY_ALL) }
    var newestFirst by remember { mutableStateOf(true) }

    val kind = if (tab == CampusStrings.LostFound.TAB_LOST) LostFoundKind.LOST else LostFoundKind.FOUND
    val filtered = remember(items, tab, keyword, category, location, newestFirst) {
        LocalLostFoundRepository.filter(items, kind, keyword, category, location, newestFirst)
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(
            title = CampusStrings.LostFound.TITLE,
            subtitle = CampusStrings.LostFound.SUBTITLE,
            onBack = onBack,
            actions = {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(PrimarySoft)
                            .campusClickable { onOpenMine() }
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                    ) {
                        Text(CampusStrings.LostFound.MINE, color = Primary, fontSize = 11.5.sp, fontWeight = FontWeight.SemiBold)
                    }
                    Spacer(Modifier.width(8.dp))
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Primary)
                            .campusClickable { onOpenPublish() },
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Add, CampusStrings.LostFound.PUBLISH, tint = androidx.compose.ui.graphics.Color.White, modifier = Modifier.size(19.dp))
                    }
                }
            },
        )
        Spacer(Modifier.height(14.dp))

        // 顶部 失物 / 招领 切换
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(13.dp))
                .background(PrimarySoft)
                .padding(4.dp),
        ) {
            listOf(CampusStrings.LostFound.TAB_LOST, CampusStrings.LostFound.TAB_FOUND).forEach { option ->
                val active = tab == option
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(10.dp))
                        .background(if (active) Primary else androidx.compose.ui.graphics.Color.Transparent)
                        .campusClickable { tab = option }
                        .padding(vertical = 9.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text(
                        option,
                        color = if (active) androidx.compose.ui.graphics.Color.White else Primary,
                        fontSize = 13.sp,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
            }
        }
        Spacer(Modifier.height(12.dp))

        // 搜索框
        Box {
            CampusTextField(
                value = keyword,
                onValueChange = { keyword = it },
                placeholder = CampusStrings.LostFound.SEARCH_HINT,
            )
            Icon(
                Icons.Default.Search,
                null,
                tint = Muted,
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .padding(end = 13.dp)
                    .size(18.dp),
            )
        }
        Spacer(Modifier.height(10.dp))
        FilterChipRow(
            options = listOf(CampusStrings.LostFound.CATEGORY_ALL) + CampusStrings.LostFound.CATEGORIES.split(","),
            selected = category,
            onSelect = { category = it },
        )
        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) {
                FormDropdown(
                    options = listOf(CampusStrings.LostFound.CATEGORY_ALL) + CampusStrings.LostFound.LOCATIONS.split(","),
                    selected = location,
                    onSelect = { location = it },
                    placeholder = "地点",
                )
            }
            Spacer(Modifier.width(10.dp))
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(12.dp))
                    .background(PrimarySoft)
                    .campusClickable { newestFirst = !newestFirst }
                    .padding(horizontal = 13.dp, vertical = 12.dp),
            ) {
                Text(
                    if (newestFirst) CampusStrings.LostFound.SORT_NEW else CampusStrings.LostFound.SORT_OLD,
                    color = Primary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
        Spacer(Modifier.height(12.dp))

        when {
            loading -> LoadingState()
            error != null -> ErrorState(
                message = error ?: CampusStrings.LostFound.LOAD_ERROR,
                onRetry = { scope.launch { repository.refresh() } },
            )
            filtered.isEmpty() -> EmptyState(Icons.Default.Inventory2, CampusStrings.LostFound.EMPTY)
            else -> LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = PaddingValues(
                    bottom = WindowInsets.navigationBars.asPaddingValues()
                        .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
                ),
            ) {
                items(filtered, key = { it.id }) { item ->
                    LostFoundCard(item, onClick = { onOpenDetail(item.id) })
                }
            }
        }
    }
}

@Composable
fun LostFoundCard(item: LostFoundItem, onClick: () -> Unit) {
    val (statusLabel, statusTone) = lostFoundStatusTag(item)
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onClick),
        padding = PaddingValues(12.dp),
    ) {
        Row {
            ItemThumbnail(item.imageUri)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        item.title,
                        color = TextPrimary,
                        fontSize = 14.sp,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(6.dp))
                    StatusTag(statusLabel, statusTone)
                }
                Spacer(Modifier.height(5.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusTag(
                        if (item.kind == LostFoundKind.LOST) CampusStrings.LostFound.KIND_LOST else CampusStrings.LostFound.KIND_FOUND,
                        if (item.kind == LostFoundKind.LOST) StatusTone.DANGER else StatusTone.SUCCESS,
                    )
                    Spacer(Modifier.width(6.dp))
                    StatusTag(item.category, StatusTone.NEUTRAL)
                }
                Spacer(Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(13.dp))
                    Spacer(Modifier.width(4.dp))
                    Text(
                        "${item.location} · ${item.time}",
                        color = Muted,
                        fontSize = 11.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
@SuppressLint("ProduceStateDoesNotAssignValue")
fun ItemThumbnail(imageUri: String?, size: androidx.compose.ui.unit.Dp = 74.dp) {
    val context = LocalContext.current
    var bitmap by remember(imageUri) { mutableStateOf<ImageBitmap?>(null) }
    LaunchedEffect(imageUri) {
        bitmap = if (imageUri != null) {
            withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.openInputStream(Uri.parse(imageUri))?.use { input ->
                        BitmapFactory.decodeStream(input)?.asImageBitmap()
                    }
                }.getOrNull()
            }
        } else null
    }
    Box(
        modifier = Modifier
            .size(size)
            .clip(RoundedCornerShape(12.dp))
            .background(PrimarySoft)
            .border(1.dp, Line, RoundedCornerShape(12.dp)),
        contentAlignment = Alignment.Center,
    ) {
        if (bitmap != null) {
            Image(
                bitmap = bitmap!!,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Icon(Icons.Default.Image, null, tint = Primary, modifier = Modifier.size(26.dp))
        }
    }
}
