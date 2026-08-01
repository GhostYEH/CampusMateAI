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
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.LocationOn
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Sort
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
import androidx.compose.ui.draw.rotate
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

@Composable
fun LostFoundScreen(repository: LostFoundRepository, onBack: () -> Unit, onOpenDetail: (Long) -> Unit, onOpenPublish: () -> Unit, onOpenMine: () -> Unit) {
    val items by repository.items.collectAsState()
    var lostTab by remember { mutableStateOf(true) }
    var keyword by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("全部") }
    var location by remember { mutableStateOf("全部地点") }
    var newestFirst by remember { mutableStateOf(true) }
    val categories = listOf("全部", "证件卡片", "电子产品", "书籍资料", "生活用品", "其他")
    val filtered = remember(items, lostTab, keyword, category, location, newestFirst) { LocalLostFoundRepository.filter(items, if (lostTab) LostFoundKind.LOST else LostFoundKind.FOUND, keyword, category, if (location == "全部地点") "全部" else location, newestFirst) }
    LazyColumn(Modifier.fillMaxSize().background(Background), contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = BottomDockReservedHeight + 18.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        item { LostHero(onBack, onOpenMine, onOpenPublish) }
        item { LostTabs(lostTab) { lostTab = it } }
        item { SearchBox(keyword) { keyword = it } }
        item { CategoryRow(categories, category) { category = it } }
        item { Row { LostDropdown(location, listOf("全部地点", "图书馆三楼", "教学楼 2-305", "食堂二楼", "体育馆观众席")) { location = it }; Spacer(Modifier.weight(1f)); SortButton(newestFirst) { newestFirst = !newestFirst } } }
        items(filtered, key = { it.id }) { item -> LostCard(item) { onOpenDetail(item.id) } }
        if (filtered.isEmpty()) item { Text("没有找到匹配的失物信息", color = Muted, fontSize = 13.sp, modifier = Modifier.padding(24.dp)) }
    }
}

@Composable private fun LostHero(onBack: () -> Unit, onMine: () -> Unit, onPublish: () -> Unit) { Box(Modifier.fillMaxWidth().height(205.dp)) { Image(painterResource(R.drawable.hero_lost_found), null, Modifier.fillMaxWidth().height(205.dp), contentScale = ContentScale.Crop, alpha = .8f); Row(Modifier.padding(top = 30.dp), verticalAlignment = Alignment.CenterVertically) { BackButton(onBack); Spacer(Modifier.width(16.dp)); Column(Modifier.weight(1f)) { Text("失物招领", color = TextPrimary, fontSize = 30.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(7.dp)); Text("本地演示数据，接入后端后可全校同步", color = Muted, fontSize = 13.sp) }; Text("我的发布", color = Primary, fontSize = 12.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clip(CircleShape).background(Surface).campusClickable { onMine() }.padding(horizontal = 13.dp, vertical = 11.dp)); Spacer(Modifier.width(8.dp)); Box(Modifier.size(48.dp).clip(CircleShape).background(Primary).campusClickable { onPublish() }, contentAlignment = Alignment.Center) { Icon(Icons.Default.Add, "发布", tint = Color.White, modifier = Modifier.size(28.dp)) } } } }
@Composable private fun BackButton(onBack: () -> Unit) { Box(Modifier.size(48.dp).clip(CircleShape).background(Surface).border(1.dp, Line, CircleShape).campusClickable { onBack() }, contentAlignment = Alignment.Center) { Icon(Icons.Default.ChevronRight, "返回", tint = TextPrimary, modifier = Modifier.size(28.dp).rotate(180f)) } }
@Composable private fun LostTabs(lost: Boolean, set: (Boolean) -> Unit) { Row(Modifier.fillMaxWidth().height(76.dp).clip(RoundedCornerShape(21.dp)).background(PrimarySoft).padding(5.dp)) { Tab("失物", lost, Modifier.weight(1f)) { set(true) }; Tab("招领", !lost, Modifier.weight(1f)) { set(false) } } }
@Composable private fun Tab(text: String, selected: Boolean, modifier: Modifier, onClick: () -> Unit) { Box(modifier.fillMaxSize().clip(RoundedCornerShape(17.dp)).background(if (selected) Primary else Color.Transparent).campusClickable(onClick = onClick), contentAlignment = Alignment.Center) { Text(text, color = if (selected) Color.White else Primary, fontSize = 17.sp, fontWeight = FontWeight.Bold) } }
@Composable private fun SearchBox(value: String, onValue: (String) -> Unit) { Row(Modifier.fillMaxWidth().height(60.dp).clip(RoundedCornerShape(18.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(18.dp)).padding(horizontal = 18.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Search, null, tint = Muted, modifier = Modifier.size(27.dp)); Spacer(Modifier.width(12.dp)); Box(Modifier.weight(1f)) { if (value.isEmpty()) Text("搜索物品、地点", color = Muted, fontSize = 15.sp); BasicTextField(value, onValue, textStyle = TextStyle(TextPrimary, fontSize = 15.sp), cursorBrush = SolidColor(Primary), modifier = Modifier.fillMaxWidth()) } } }
@Composable private fun CategoryRow(options: List<String>, selected: String, onSelect: (String) -> Unit) { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(7.dp)) { options.forEach { option -> Box(Modifier.weight(1f).clip(CircleShape).background(if (option == selected) PrimarySoft else Surface).border(1.dp, if (option == selected) Primary else Line, CircleShape).campusClickable { onSelect(option) }.padding(vertical = 10.dp), contentAlignment = Alignment.Center) { Text(option, color = if (option == selected) Primary else Muted, fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, maxLines = 1) } } } }
@Composable private fun LostDropdown(selected: String, options: List<String>, onSelect: (String) -> Unit) { var expanded by remember { mutableStateOf(false) }; Box { Row(Modifier.width(170.dp).clip(RoundedCornerShape(15.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(15.dp)).campusClickable { expanded = true }.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) { Text(selected, color = TextPrimary, fontSize = 12.sp, modifier = Modifier.weight(1f)); Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(20.dp).rotate(90f)) }; DropdownMenu(expanded, { expanded = false }) { options.forEach { option -> DropdownMenuItem({ Text(option) }, { onSelect(option); expanded = false }) } } } }
@Composable private fun SortButton(newest: Boolean, onClick: () -> Unit) { Row(Modifier.clip(RoundedCornerShape(15.dp)).background(Surface).border(1.dp, Line, RoundedCornerShape(15.dp)).campusClickable(onClick = onClick).padding(horizontal = 13.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Sort, null, tint = Muted, modifier = Modifier.size(20.dp)); Spacer(Modifier.width(7.dp)); Text(if (newest) "最新优先" else "最早优先", color = TextPrimary, fontSize = 12.sp) } }
@Composable private fun LostCard(item: LostFoundItem, onClick: () -> Unit) { Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(22.dp)).background(Surface).campusClickable(onClick = onClick).padding(14.dp), verticalAlignment = Alignment.CenterVertically) { LostImage(item); Spacer(Modifier.width(14.dp)); Column(Modifier.weight(1f)) { Row(verticalAlignment = Alignment.CenterVertically) { Text(item.title, color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f)); Text(if (item.status == LostFoundStatus.CLOSED) "已结束" else if (item.kind == LostFoundKind.LOST) "寻找中" else "待认领", color = if (item.status == LostFoundStatus.CLOSED) Muted else Color(0xFFEF7942), fontSize = 11.5.sp, fontWeight = FontWeight.Bold, modifier = Modifier.clip(CircleShape).background(if (item.status == LostFoundStatus.CLOSED) PrimarySoft else Color(0xFFFFF0E9)).padding(horizontal = 10.dp, vertical = 7.dp)) }; Spacer(Modifier.height(8.dp)); Row { Pill(if (item.kind == LostFoundKind.LOST) "丢失物品" else "招领物品", if (item.kind == LostFoundKind.LOST) Color(0xFFFFEDE8) else Color(0xFFEAF9F3), if (item.kind == LostFoundKind.LOST) Color(0xFFE35F42) else Color(0xFF36A67D)); Spacer(Modifier.width(7.dp)); Pill(item.category, PrimarySoft, Primary) }; Spacer(Modifier.height(8.dp)); Row(verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.LocationOn, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" ${item.location}", color = Muted, fontSize = 11.sp); Spacer(Modifier.width(7.dp)); Text("·", color = Muted); Spacer(Modifier.width(7.dp)); Icon(Icons.Default.Schedule, null, tint = Muted, modifier = Modifier.size(14.dp)); Text(" ${item.time}", color = Muted, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) }; Spacer(Modifier.height(7.dp)); Text(item.description, color = Muted, fontSize = 11.5.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) } } }
@Composable private fun Pill(text: String, bg: Color, fg: Color) { Text(text, color = fg, fontSize = 10.5.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.clip(CircleShape).background(bg).padding(horizontal = 9.dp, vertical = 5.dp)) }
@Composable @SuppressLint("ProduceStateDoesNotAssignValue") private fun LostImage(item: LostFoundItem) { val context = LocalContext.current; var userImage by remember(item.imageUri) { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }; LaunchedEffect(item.imageUri) { userImage = item.imageUri?.let { uri -> withContext(Dispatchers.IO) { runCatching { context.contentResolver.openInputStream(Uri.parse(uri))?.use { BitmapFactory.decodeStream(it)?.asImageBitmap() } }.getOrNull() } } }; val resource = when { item.title.contains("充电") -> R.drawable.lost_power_bank; item.title.contains("深度") -> R.drawable.lost_book; item.title.contains("校园卡") -> R.drawable.lost_card; item.title.contains("耳机") -> R.drawable.lost_earbuds; else -> R.drawable.hero_lost_found }; Box(Modifier.size(100.dp).clip(RoundedCornerShape(16.dp)).background(PrimarySoft)) { if (userImage != null) Image(userImage!!, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) else Image(painterResource(resource), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) } }
