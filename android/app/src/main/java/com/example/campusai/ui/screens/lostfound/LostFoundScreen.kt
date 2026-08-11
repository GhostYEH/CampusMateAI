package com.example.campusai.ui.screens.lostfound

import android.annotation.SuppressLint
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowBackIosNew
import androidx.compose.material.icons.filled.Campaign
import androidx.compose.material.icons.filled.FilterList
import androidx.compose.material.icons.filled.Inventory2
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.R
import com.example.campusai.data.model.LostFoundItem
import com.example.campusai.data.model.LostFoundKind
import com.example.campusai.data.model.LostFoundStatus
import com.example.campusai.data.repository.LocalLostFoundRepository
import com.example.campusai.data.repository.LostFoundRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val LostCategories = listOf("全部", "证件卡片", "电子产品", "书籍资料", "生活用品", "其他")

@Composable
fun LostFoundScreen(
    repository: LostFoundRepository,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
    onOpenPublish: () -> Unit,
    onOpenMine: () -> Unit,
) {
    val items by repository.items.collectAsState()
    var browseState by remember { mutableStateOf(LostFoundBrowseState()) }
    val filtered = remember(items, browseState) {
        LocalLostFoundRepository.filter(
            items = items,
            kind = browseState.kind,
            keyword = browseState.keyword,
            category = browseState.category,
            location = browseState.repositoryLocation(),
            newestFirst = browseState.newestFirst,
        )
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(Background),
        contentPadding = PaddingValues(bottom = BottomDockReservedHeight + 20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            LostHero(
                onBack = onBack,
                onMine = onOpenMine,
                onPublish = onOpenPublish,
            )
        }
        item {
            LostModeSwitch(
                selectedKind = browseState.kind,
                onSelect = { browseState = browseState.copy(kind = it) },
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
        item {
            SearchBox(
                value = browseState.keyword,
                onValueChange = { browseState = browseState.copy(keyword = it) },
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
        item {
            CategoryRow(
                categories = LostCategories,
                selected = browseState.category,
                onSelect = { browseState = browseState.copy(category = it) },
            )
        }
        item {
            FilterControls(
                location = browseState.location,
                newestFirst = browseState.newestFirst,
                onLocationChange = { browseState = browseState.copy(location = it) },
                onSortToggle = {
                    browseState = browseState.copy(newestFirst = !browseState.newestFirst)
                },
            )
        }
        items(filtered, key = { it.id }) { item ->
            LostCard(
                item = item,
                onClick = { onOpenDetail(item.id) },
                modifier = Modifier.padding(horizontal = 16.dp),
            )
        }
        if (filtered.isEmpty()) {
            item {
                EmptyResults(
                    modifier = Modifier.padding(horizontal = 16.dp, vertical = 28.dp),
                )
            }
        }
    }
}

@Composable
private fun LostHero(
    onBack: () -> Unit,
    onMine: () -> Unit,
    onPublish: () -> Unit,
) {
    val heroShape = RoundedCornerShape(bottomStart = 34.dp, bottomEnd = 34.dp)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(278.dp)
            .clip(heroShape)
            .background(
                Brush.linearGradient(
                    colors = listOf(
                        Color(0xFFE5E9FF),
                        Color(0xFFF3F5FF),
                        Color(0xFFFBFCFF),
                    ),
                ),
            ),
    ) {
        Image(
            painter = painterResource(R.drawable.hero_lost_found),
            contentDescription = null,
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .align(Alignment.BottomEnd)
                .offset(x = 10.dp, y = 4.dp)
                .width(272.dp)
                .height(252.dp),
        )
        Box(
            modifier = Modifier
                .padding(start = 20.dp, top = 18.dp)
                .size(52.dp)
                .clip(CircleShape)
                .background(Surface.copy(alpha = .78f))
                .border(1.dp, Color.White.copy(alpha = .72f), CircleShape)
                .campusClickable(onClick = onBack),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = Icons.Default.ArrowBackIosNew,
                contentDescription = "返回",
                tint = TextPrimary,
                modifier = Modifier.size(20.dp),
            )
        }
        Row(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(top = 20.dp, end = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = "我的发布",
                color = Primary,
                fontSize = 15.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Surface.copy(alpha = .82f))
                    .border(1.dp, Color.White.copy(alpha = .9f), CircleShape)
                    .campusClickable(onClick = onMine)
                    .padding(horizontal = 18.dp, vertical = 12.dp),
            )
            Spacer(Modifier.width(10.dp))
            Box(
                modifier = Modifier
                    .size(52.dp)
                    .clip(CircleShape)
                    .background(Primary)
                    .shadow(12.dp, CircleShape, clip = false)
                    .campusClickable(onClick = onPublish),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "发布",
                    tint = Color.White,
                    modifier = Modifier.size(31.dp),
                )
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(start = 24.dp, bottom = 33.dp)
                .width(220.dp),
        ) {
            Text(
                text = "失物招领",
                color = Color(0xFF182555),
                fontSize = 36.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp,
            )
            Spacer(Modifier.height(10.dp))
            Text(
                text = "本地显示数据，接入后端后\n可全校同步",
                color = Color(0xFF536888),
                fontSize = 15.sp,
                lineHeight = 24.sp,
            )
        }
    }
}

@Composable
private fun LostModeSwitch(
    selectedKind: LostFoundKind,
    onSelect: (LostFoundKind) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(70.dp)
            .clip(RoundedCornerShape(26.dp))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .7f), RoundedCornerShape(26.dp))
            .padding(5.dp),
    ) {
        ModeSegment(
            label = "失物",
            icon = Icons.Default.Inventory2,
            selected = selectedKind == LostFoundKind.LOST,
            onClick = { onSelect(LostFoundKind.LOST) },
            modifier = Modifier.weight(1f),
        )
        ModeSegment(
            label = "招领",
            icon = Icons.Default.Campaign,
            selected = selectedKind == LostFoundKind.FOUND,
            onClick = { onSelect(LostFoundKind.FOUND) },
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun ModeSegment(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    selected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier,
) {
    Row(
        modifier = modifier
            .height(60.dp)
            .clip(RoundedCornerShape(21.dp))
            .background(if (selected) Primary else Color.Transparent)
            .campusClickable(onClick = onClick),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = if (selected) Color.White else Primary,
            modifier = Modifier.size(27.dp),
        )
        Spacer(Modifier.width(10.dp))
        Text(
            text = label,
            color = if (selected) Color.White else Primary,
            fontSize = 18.sp,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun SearchBox(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .height(60.dp)
            .clip(RoundedCornerShape(23.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(23.dp))
            .padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Default.Search,
            contentDescription = null,
            tint = Muted,
            modifier = Modifier.size(26.dp),
        )
        Spacer(Modifier.width(12.dp))
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) {
                Text("搜索物品、地点", color = Muted, fontSize = 15.sp)
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                textStyle = TextStyle(color = TextPrimary, fontSize = 15.sp),
                cursorBrush = SolidColor(Primary),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
        }
    }
}

@Composable
private fun CategoryRow(
    categories: List<String>,
    selected: String,
    onSelect: (String) -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState())
            .padding(horizontal = 16.dp),
        horizontalArrangement = Arrangement.spacedBy(9.dp),
    ) {
        categories.forEach { category ->
            val active = category == selected
            Text(
                text = category,
                color = if (active) Color.White else TextPrimary,
                fontSize = 14.sp,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(if (active) Primary else Surface)
                    .border(
                        1.dp,
                        if (active) Primary else Line,
                        CircleShape,
                    )
                    .campusClickable { onSelect(category) }
                    .padding(horizontal = 17.dp, vertical = 12.dp),
            )
        }
    }
}

@Composable
private fun FilterControls(
    location: String,
    newestFirst: Boolean,
    onLocationChange: (String) -> Unit,
    onSortToggle: () -> Unit,
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp),
    ) {
        if (maxWidth < 360.dp) {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                LocationDropdown(
                    selected = location,
                    onSelect = onLocationChange,
                    modifier = Modifier.fillMaxWidth(),
                )
                SortButton(
                    newestFirst = newestFirst,
                    onClick = onSortToggle,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        } else {
            Row(
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.fillMaxWidth(),
            ) {
                LocationDropdown(
                    selected = location,
                    onSelect = onLocationChange,
                    modifier = Modifier.width(166.dp),
                )
                SortButton(newestFirst = newestFirst, onClick = onSortToggle)
            }
        }
    }
}

@Composable
private fun LocationDropdown(
    selected: String,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Row(
            modifier = modifier
                .height(58.dp)
                .clip(RoundedCornerShape(18.dp))
                .background(Surface)
                .border(1.dp, Line, RoundedCornerShape(18.dp))
                .campusClickable { expanded = true }
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(9.dp))
            Text(
                text = selected,
                color = TextPrimary,
                fontSize = 14.sp,
                maxLines = 1,
                modifier = Modifier.weight(1f),
            )
            Icon(Icons.Default.KeyboardArrowDown, null, tint = Muted, modifier = Modifier.size(20.dp))
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            LostFoundBrowseOptions.locations.forEach { location ->
                DropdownMenuItem(
                    text = { Text(location) },
                    onClick = {
                        onSelect(location)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun SortButton(
    newestFirst: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .height(58.dp)
            .clip(RoundedCornerShape(18.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(18.dp))
            .campusClickable(onClick = onClick)
            .padding(horizontal = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.FilterList, null, tint = Muted, modifier = Modifier.size(21.dp))
        Spacer(Modifier.width(8.dp))
        Text(
            text = if (newestFirst) "最新优先" else "最早优先",
            color = TextPrimary,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.width(5.dp))
        Icon(Icons.Default.KeyboardArrowDown, null, tint = Muted, modifier = Modifier.size(19.dp))
    }
}

@Composable
private fun LostCard(
    item: LostFoundItem,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(28.dp))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .55f), RoundedCornerShape(28.dp))
            .campusClickable(onClick = onClick)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        LostImage(item)
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = item.title,
                    color = TextPrimary,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                StatusChip(item)
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                ItemChip(
                    text = if (item.kind == LostFoundKind.LOST) "失物招领" else "招领物品",
                    background = if (item.kind == LostFoundKind.LOST) Color(0xFFFFEEE8) else Color(0xFFEAF9F3),
                    foreground = if (item.kind == LostFoundKind.LOST) Color(0xFFF06B45) else Color(0xFF339474),
                )
                ItemChip(
                    text = item.category,
                    background = PrimarySoft,
                    foreground = Primary,
                )
            }
            Spacer(Modifier.height(10.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    text = item.location,
                    color = Muted,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Spacer(Modifier.width(9.dp))
                Text("│", color = Line, fontSize = 13.sp)
                Spacer(Modifier.width(9.dp))
                Icon(Icons.Default.Schedule, null, tint = Muted, modifier = Modifier.size(17.dp))
                Spacer(Modifier.width(4.dp))
                Text(
                    text = item.time,
                    color = Muted,
                    fontSize = 13.sp,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
            }
            Spacer(Modifier.height(9.dp))
            Text(
                text = item.description,
                color = Muted,
                fontSize = 13.sp,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun StatusChip(item: LostFoundItem) {
    val closed = item.status == LostFoundStatus.CLOSED
    Text(
        text = when {
            closed && item.kind == LostFoundKind.LOST -> "已找到"
            closed -> "已归还"
            item.kind == LostFoundKind.LOST -> "寻找中"
            else -> "待认领"
        },
        color = if (closed) Muted else Color(0xFFF06B45),
        fontSize = 13.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier
            .clip(CircleShape)
            .background(if (closed) PrimarySoft else Color(0xFFFFF0EA))
            .padding(horizontal = 12.dp, vertical = 8.dp),
    )
}

@Composable
private fun ItemChip(
    text: String,
    background: Color,
    foreground: Color,
) {
    Text(
        text = text,
        color = foreground,
        fontSize = 12.sp,
        fontWeight = FontWeight.SemiBold,
        maxLines = 1,
        modifier = Modifier
            .clip(CircleShape)
            .background(background)
            .padding(horizontal = 10.dp, vertical = 7.dp),
    )
}

@Composable
private fun EmptyResults(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Surface)
            .border(1.dp, Line, RoundedCornerShape(24.dp))
            .padding(vertical = 34.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(Icons.Default.Search, null, tint = Primary, modifier = Modifier.size(28.dp))
        Spacer(Modifier.height(10.dp))
        Text("没有找到匹配的失物信息", color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.height(4.dp))
        Text("换个关键词或筛选条件试试", color = Muted, fontSize = 13.sp)
    }
}

@Composable
@SuppressLint("ProduceStateDoesNotAssignValue")
private fun LostImage(item: LostFoundItem) {
    val context = LocalContext.current
    var userImage by remember(item.imageUri) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }

    LaunchedEffect(item.imageUri) {
        userImage = item.imageUri?.let { uri ->
            withContext(Dispatchers.IO) {
                runCatching {
                    context.contentResolver.openInputStream(Uri.parse(uri))?.use { input ->
                        BitmapFactory.decodeStream(input)?.asImageBitmap()
                    }
                }.getOrNull()
            }
        }
    }

    val resource = when {
        item.title.contains("充电") -> R.drawable.lost_power_bank
        item.title.contains("深度") -> R.drawable.lost_book
        item.title.contains("校园卡") -> R.drawable.lost_card
        item.title.contains("耳机") || item.title.contains("AirPods") -> R.drawable.lost_earbuds
        else -> R.drawable.hero_lost_found
    }
    Box(
        modifier = Modifier
            .size(112.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(PrimarySoft),
        contentAlignment = Alignment.Center,
    ) {
        if (userImage != null) {
            Image(
                bitmap = userImage!!,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } else {
            Image(
                painter = painterResource(resource),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}
