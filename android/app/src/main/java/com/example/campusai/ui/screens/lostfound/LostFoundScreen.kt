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
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.lifecycle.compose.collectAsStateWithLifecycle
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

private val PagePadding = 16.dp
private val HeroHeight = 300.dp
private val HeroRadius = 34.dp
private val FilterRadius = 28.dp
private val ItemCardRadius = 26.dp
private val ItemImageSize = 112.dp
private val SectionSpacing = 12.dp

internal fun lostFoundCategoryChipHorizontalPaddingDp(screenWidthDp: Int): Float =
    if (screenWidthDp <= 432) 9f else 12f

@Composable
fun LostFoundScreen(
    repository: LostFoundRepository,
    onBack: () -> Unit,
    onOpenDetail: (Long) -> Unit,
    onOpenPublish: () -> Unit,
    onOpenMine: () -> Unit,
) {
    val items by repository.items.collectAsStateWithLifecycle()
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
            .background(Color(0xFFF6F8FC)),
        contentPadding = PaddingValues(bottom = BottomDockReservedHeight + 20.dp),
        verticalArrangement = Arrangement.spacedBy(SectionSpacing),
    ) {
        item {
            LostHero(
                onBack = onBack,
                onMine = onOpenMine,
                onPublish = onOpenPublish,
            )
        }
        item {
            Column(
                modifier = Modifier
                    .padding(horizontal = PagePadding)
                    .fillMaxWidth()
                    .shadow(8.dp, RoundedCornerShape(FilterRadius), ambientColor = Primary.copy(alpha = .08f), spotColor = Primary.copy(alpha = .06f))
                    .clip(RoundedCornerShape(FilterRadius))
                    .background(Surface.copy(alpha = .96f))
                    .border(1.dp, Color.White, RoundedCornerShape(FilterRadius))
                    .padding(horizontal = 10.dp, vertical = 10.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                LostModeSwitch(
                    selectedKind = browseState.kind,
                    onSelect = { browseState = browseState.copy(kind = it) },
                )
                SearchBox(
                    value = browseState.keyword,
                    onValueChange = { browseState = browseState.copy(keyword = it) },
                )
                CategoryRow(
                    categories = LostCategories,
                    selected = browseState.category,
                    onSelect = { browseState = browseState.copy(category = it) },
                    contentPadding = PaddingValues(0.dp),
                )
                FilterControls(
                    location = browseState.location,
                    newestFirst = browseState.newestFirst,
                    onLocationChange = { browseState = browseState.copy(location = it) },
                    onSortToggle = {
                        browseState = browseState.copy(newestFirst = !browseState.newestFirst)
                    },
                    contentPadding = PaddingValues(0.dp),
                )
            }
        }
        itemsIndexed(filtered, key = { index, item -> "lost-found|${item.id}|$index" }) { _, item ->
            LostCard(
                item = item,
                onClick = { onOpenDetail(item.id) },
                modifier = Modifier.padding(horizontal = PagePadding),
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
    val heroShape = RoundedCornerShape(bottomStart = HeroRadius, bottomEnd = HeroRadius)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(HeroHeight)
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
                .fillMaxSize(),
        )
        Row(
            modifier = Modifier
                .align(Alignment.TopStart)
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(start = 20.dp, top = 14.dp, end = 18.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(46.dp)
                    .shadow(7.dp, CircleShape, ambientColor = Primary.copy(alpha = .07f), spotColor = Primary.copy(alpha = .06f))
                    .clip(CircleShape)
                    .background(Surface.copy(alpha = .68f))
                    .border(1.dp, Color.White.copy(alpha = .72f), CircleShape)
                    .campusClickable(onClick = onBack),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Default.ArrowBackIosNew,
                    contentDescription = "返回",
                    tint = Color(0xFF1A2B54),
                    modifier = Modifier.size(20.dp),
                )
            }
            Spacer(Modifier.width(14.dp))
            Text(
                text = "失物招领",
                color = Color(0xFF142443),
                fontSize = 21.sp,
                fontWeight = FontWeight.Bold,
            )
            Spacer(Modifier.weight(1f))
            Text(
                text = "我的发布",
                color = Primary,
                fontSize = 14.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier
                    .clip(CircleShape)
                    .background(Surface.copy(alpha = .82f))
                    .border(1.dp, Color.White.copy(alpha = .9f), CircleShape)
                    .campusClickable(onClick = onMine)
                    .padding(horizontal = 17.dp, vertical = 11.dp),
            )
            Spacer(Modifier.width(9.dp))
            Box(
                modifier = Modifier
                    .size(48.dp)
                    .shadow(12.dp, CircleShape, ambientColor = Primary.copy(alpha = .18f), spotColor = Primary.copy(alpha = .14f))
                    .clip(CircleShape)
                    .background(Primary)
                    .campusClickable(onClick = onPublish),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    imageVector = Icons.Default.Add,
                    contentDescription = "发布",
                    tint = Color.White,
                    modifier = Modifier.size(29.dp),
                )
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.BottomStart)
                .padding(start = 28.dp, bottom = 38.dp)
                .width(180.dp),
        ) {
            Text(
                text = "失物招领",
                color = Color(0xFF182555),
                fontSize = 35.sp,
                fontWeight = FontWeight.Black,
                letterSpacing = 1.sp,
            )
            Spacer(Modifier.height(12.dp))
            Text(
                text = "本地显示数据，接入后端后\n可全校同步",
                color = Color(0xFF536888),
                fontSize = 14.sp,
                lineHeight = 22.sp,
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
            .height(52.dp)
            .clip(RoundedCornerShape(22.dp))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .6f), RoundedCornerShape(22.dp))
            .padding(3.dp),
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
            .height(46.dp)
            .clip(RoundedCornerShape(19.dp))
            .background(if (selected) Primary else Color.Transparent)
            .campusClickable(onClick = onClick),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = label,
            tint = if (selected) Color.White else Primary,
            modifier = Modifier.size(22.dp),
        )
        Spacer(Modifier.width(9.dp))
        Text(
            text = label,
            color = if (selected) Color.White else Primary,
            fontSize = 16.sp,
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
            .height(48.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(20.dp))
            .padding(horizontal = 18.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            imageVector = Icons.Default.Search,
            contentDescription = null,
            tint = Muted,
            modifier = Modifier.size(23.dp),
        )
        Spacer(Modifier.width(12.dp))
        Box(Modifier.weight(1f)) {
            if (value.isEmpty()) {
                Text("搜索物品、地点", color = Muted, fontSize = 14.sp)
            }
            BasicTextField(
                value = value,
                onValueChange = onValueChange,
                textStyle = TextStyle(color = TextPrimary, fontSize = 14.sp),
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
    contentPadding: PaddingValues = PaddingValues(horizontal = 16.dp),
) {
    BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val chipHorizontalPadding =
            lostFoundCategoryChipHorizontalPaddingDp(maxWidth.value.toInt()).dp
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState())
                .padding(contentPadding),
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            categories.forEach { category ->
                val active = category == selected
                Text(
                    text = category,
                    color = if (active) Color.White else TextPrimary,
                    fontSize = 11.5.sp,
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
                        .padding(horizontal = chipHorizontalPadding, vertical = 8.dp),
                )
            }
        }
    }
}

@Composable
private fun FilterControls(
    location: String,
    newestFirst: Boolean,
    onLocationChange: (String) -> Unit,
    onSortToggle: () -> Unit,
    contentPadding: PaddingValues = PaddingValues(horizontal = 16.dp),
) {
    BoxWithConstraints(
        modifier = Modifier
            .fillMaxWidth()
            .padding(contentPadding),
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
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(12.dp))
                SortButton(
                    newestFirst = newestFirst,
                    onClick = onSortToggle,
                    modifier = Modifier.weight(.92f),
                )
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
    Box(modifier = modifier) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .height(46.dp)
                .clip(RoundedCornerShape(17.dp))
                .background(Surface)
                .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(17.dp))
                .campusClickable { expanded = true }
                .padding(horizontal = 16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(20.dp))
            Spacer(Modifier.width(9.dp))
            Text(
                text = selected,
                color = TextPrimary,
                fontSize = 13.sp,
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
            .height(46.dp)
            .clip(RoundedCornerShape(17.dp))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(17.dp))
            .campusClickable(onClick = onClick)
            .padding(horizontal = 15.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.FilterList, null, tint = Muted, modifier = Modifier.size(21.dp))
        Spacer(Modifier.width(8.dp))
        Text(
            text = if (newestFirst) "最新优先" else "最早优先",
            color = TextPrimary,
            fontSize = 13.sp,
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
            .shadow(5.dp, RoundedCornerShape(ItemCardRadius), ambientColor = Primary.copy(alpha = .05f), spotColor = Primary.copy(alpha = .04f))
            .clip(RoundedCornerShape(ItemCardRadius))
            .background(Surface)
            .border(1.dp, Line.copy(alpha = .45f), RoundedCornerShape(ItemCardRadius))
            .campusClickable(onClick = onClick)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        LostImage(item)
        Spacer(Modifier.width(14.dp))
        Column(modifier = Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = item.title,
                    color = TextPrimary,
                    fontSize = 17.sp,
                    fontWeight = FontWeight.Bold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                Spacer(Modifier.width(8.dp))
                StatusChip(item)
            }
            Spacer(Modifier.height(8.dp))
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
            Spacer(Modifier.height(8.dp))
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
            Spacer(Modifier.height(7.dp))
            Text(
                text = item.description,
                color = Muted,
                fontSize = 13.sp,
                maxLines = 2,
                lineHeight = 18.sp,
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
        fontSize = 12.sp,
        fontWeight = FontWeight.Bold,
        modifier = Modifier
            .clip(CircleShape)
            .background(if (closed) PrimarySoft else Color(0xFFFFF0EA))
            .padding(horizontal = 11.dp, vertical = 7.dp),
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
            .size(ItemImageSize)
            .clip(RoundedCornerShape(20.dp))
            .background(PrimarySoft),
        contentAlignment = Alignment.Center,
    ) {
        userImage?.let { image ->
            Image(
                bitmap = image,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        } ?: run {
            Image(
                painter = painterResource(resource),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize(),
            )
        }
    }
}
