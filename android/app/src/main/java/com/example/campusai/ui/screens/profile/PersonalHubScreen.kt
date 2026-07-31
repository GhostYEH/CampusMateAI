package com.example.campusai.ui.screens.profile

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.model.CampusActivity
import com.example.campusai.data.model.CampusFile
import com.example.campusai.data.model.FavoriteItem
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private enum class PersonalSection(val label: String, val icon: ImageVector) {
    Files("文件", Icons.Default.FolderOpen),
    Activities("活动", Icons.Default.EventAvailable),
    Favorites("收藏", Icons.Default.Bookmark),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PersonalHubScreen(
    repository: AppRepository,
    initialSection: String,
    onBack: () -> Unit,
    onNavigate: (String) -> Unit,
) {
    val files by repository.files.collectAsState()
    val activities by repository.activities.collectAsState()
    val favorites by repository.favorites.collectAsState()
    val loading by repository.personalHubLoading.collectAsState()
    val reduceMotion by repository.reduceMotion.collectAsState()
    val scope = rememberCoroutineScope()
    val snackbar = remember { SnackbarHostState() }
    var sectionName by remember(initialSection) { mutableStateOf(initialSection) }
    var query by remember { mutableStateOf("") }
    var showAddFile by remember { mutableStateOf(false) }
    val section = when (sectionName) {
        "activities" -> PersonalSection.Activities
        "favorites" -> PersonalSection.Favorites
        else -> PersonalSection.Files
    }

    Scaffold(
        containerColor = Background,
        contentWindowInsets = WindowInsets(0, 0, 0, 0),
        snackbarHost = { SnackbarHost(snackbar) },
    ) { inner ->
        Box(Modifier.fillMaxSize().padding(inner).background(Background)) {
            Column(Modifier.fillMaxSize()) {
                PersonalHubHeader(section.label, onBack)
            PersonalSectionTabs(
                selected = section,
                onSelected = {
                    sectionName = when (it) {
                        PersonalSection.Files -> "files"
                        PersonalSection.Activities -> "activities"
                        PersonalSection.Favorites -> "favorites"
                    }
                    query = ""
                },
            )
            SearchField(
                value = query,
                onValueChange = { query = it },
                placeholder = when (section) {
                    PersonalSection.Files -> "搜索文件名、课程或来源"
                    PersonalSection.Activities -> "搜索活动、地点或主办方"
                    PersonalSection.Favorites -> "搜索已收藏内容"
                },
            )
            AnimatedContent(
                targetState = section to loading,
                transitionSpec = {
                    if (reduceMotion) fadeIn() togetherWith fadeOut()
                    else {
                        val forward = targetState.first.ordinal > initialState.first.ordinal
                        (slideInHorizontally { if (forward) it / 4 else -it / 4 } + fadeIn()) togetherWith
                            (slideOutHorizontally { if (forward) -it / 4 else it / 4 } + fadeOut())
                    }
                },
                label = "personal-section",
                modifier = Modifier.weight(1f),
            ) { (target, isLoading) ->
                if (isLoading) {
                    PersonalHubLoading()
                } else when (target) {
                    PersonalSection.Files -> FileList(
                        files = files.filter {
                            query.isBlank() || listOf(it.name, it.category, it.source)
                                .any { field -> field.contains(query, ignoreCase = true) }
                        },
                        reduceMotion = reduceMotion,
                        onFavorite = { id ->
                            scope.launch {
                                repository.toggleFileFavorite(id)
                                snackbar.showSnackbar("收藏状态已更新")
                            }
                        },
                        onDelete = { id ->
                            scope.launch {
                                repository.deleteFile(id)
                                snackbar.showSnackbar("文件记录已移除")
                            }
                        },
                    )
                    PersonalSection.Activities -> ActivityList(
                        activities = activities.filter {
                            query.isBlank() || listOf(it.title, it.organizer, it.location)
                                .any { field -> field.contains(query, ignoreCase = true) }
                        },
                        reduceMotion = reduceMotion,
                        onJoin = { id ->
                            scope.launch {
                                repository.toggleActivityJoined(id)
                                snackbar.showSnackbar("报名状态已更新")
                            }
                        },
                        onFavorite = { id ->
                            scope.launch {
                                repository.toggleActivityFavorite(id)
                                snackbar.showSnackbar("收藏状态已更新")
                            }
                        },
                    )
                    PersonalSection.Favorites -> FavoriteList(
                        favorites = favorites.filter {
                            query.isBlank() || listOf(it.title, it.type, it.subtitle)
                                .any { field -> field.contains(query, ignoreCase = true) }
                        },
                        reduceMotion = reduceMotion,
                        onOpen = { favorite -> onNavigate(favorite.sourceRoute) },
                        onRemove = { id ->
                            scope.launch {
                                repository.removeFavorite(id)
                                snackbar.showSnackbar("已取消收藏")
                            }
                        },
                    )
                }
            }
            }

            if (section == PersonalSection.Files) {
                SmallFloatingActionButton(
                    onClick = { showAddFile = true },
                    containerColor = Primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary,
                    shape = RoundedCornerShape(16.dp),
                    modifier = Modifier
                        .align(Alignment.BottomEnd)
                        .padding(end = 18.dp, bottom = BottomDockReservedHeight + 12.dp),
                ) {
                    Icon(Icons.Default.Add, "添加文件记录")
                }
            }
        }
    }

    if (showAddFile) {
        AddFileSheet(
            onDismiss = { showAddFile = false },
            onAdd = { name, category ->
                scope.launch {
                    repository.addFile(name, category)
                    showAddFile = false
                    snackbar.showSnackbar("文件记录已保存到当前账号")
                }
            },
        )
    }
}

@Composable
private fun PersonalHubLoading() {
    Column(
        Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        CircularProgressIndicator(color = Primary, strokeWidth = 3.dp, modifier = Modifier.size(30.dp))
        Spacer(Modifier.height(12.dp))
        Text("正在读取当前账号内容", color = Muted, fontSize = 12.sp)
    }
}

@Composable
private fun PersonalHubHeader(title: String, onBack: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        IconButton(onClick = onBack) {
            Icon(Icons.Default.ArrowBack, "返回", tint = TextPrimary)
        }
        Column(Modifier.padding(start = 4.dp)) {
            Text("我的$title", color = TextPrimary, fontSize = 23.sp, fontWeight = FontWeight.Bold)
            Text("内容仅保存在当前登录账号下", color = Muted, fontSize = 11.sp)
        }
    }
}

@Composable
private fun PersonalSectionTabs(selected: PersonalSection, onSelected: (PersonalSection) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)
            .clip(RoundedCornerShape(18.dp)).background(Surface).padding(5.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        PersonalSection.entries.forEach { section ->
            val active = section == selected
            Row(
                Modifier.weight(1f).height(42.dp).clip(RoundedCornerShape(14.dp))
                    .background(if (active) PrimarySoft else Color.Transparent)
                    .campusClickable { onSelected(section) },
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.Center,
            ) {
                Icon(
                    section.icon,
                    null,
                    tint = if (active) Primary else Muted,
                    modifier = Modifier.size(18.dp),
                )
                Spacer(Modifier.width(6.dp))
                Text(
                    section.label,
                    color = if (active) Primary else Muted,
                    fontWeight = if (active) FontWeight.Bold else FontWeight.Medium,
                    fontSize = 13.sp,
                )
            }
        }
    }
}

@Composable
private fun SearchField(value: String, onValueChange: (String) -> Unit, placeholder: String) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
        placeholder = { Text(placeholder, fontSize = 13.sp) },
        leadingIcon = { Icon(Icons.Default.Search, null, Modifier.size(20.dp)) },
        trailingIcon = if (value.isNotEmpty()) {
            {
                IconButton(onClick = { onValueChange("") }) {
                    Icon(Icons.Default.Close, "清空搜索", Modifier.size(18.dp))
                }
            }
        } else null,
        singleLine = true,
        shape = RoundedCornerShape(16.dp),
        colors = OutlinedTextFieldDefaults.colors(
            focusedContainerColor = Surface,
            unfocusedContainerColor = Surface,
            focusedBorderColor = Primary,
            unfocusedBorderColor = Line,
        ),
    )
}

@Composable
private fun FileList(
    files: List<CampusFile>,
    reduceMotion: Boolean,
    onFavorite: (Long) -> Unit,
    onDelete: (Long) -> Unit,
) {
    ContentList(
        empty = files.isEmpty(),
        emptyIcon = Icons.Default.FolderOff,
        emptyTitle = "没有找到文件",
        emptyHint = "换个关键词，或添加一条文件记录",
    ) {
        items(files, key = { it.id }) { file ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 5.dp)
                    .clip(RoundedCornerShape(18.dp)).background(Surface)
                    .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(18.dp))
                    .padding(start = 14.dp, top = 13.dp, bottom = 13.dp, end = 4.dp)
                    .enterAnimation(enabled = !reduceMotion),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier.size(46.dp).clip(RoundedCornerShape(14.dp)).background(PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(fileIcon(file.name), null, tint = Primary, modifier = Modifier.size(23.dp))
                }
                Column(Modifier.padding(start = 12.dp).weight(1f)) {
                    Text(
                        file.name,
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Spacer(Modifier.height(4.dp))
                    Text("${file.category} · ${file.sizeLabel}", color = Muted, fontSize = 11.sp)
                    Text("${file.updatedAt} · ${file.source}", color = Muted.copy(alpha = .8f), fontSize = 10.sp)
                }
                IconButton(onClick = { onFavorite(file.id) }) {
                    Icon(
                        if (file.isFavorite) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                        if (file.isFavorite) "取消收藏" else "收藏",
                        tint = if (file.isFavorite) Accent else Muted,
                    )
                }
                IconButton(onClick = { onDelete(file.id) }) {
                    Icon(Icons.Default.DeleteOutline, "删除记录", tint = Muted)
                }
            }
        }
    }
}

@Composable
private fun ActivityList(
    activities: List<CampusActivity>,
    reduceMotion: Boolean,
    onJoin: (Long) -> Unit,
    onFavorite: (Long) -> Unit,
) {
    ContentList(
        empty = activities.isEmpty(),
        emptyIcon = Icons.Default.EventBusy,
        emptyTitle = "没有找到活动",
        emptyHint = "换个关键词看看校园里还有什么",
    ) {
        items(activities, key = { it.id }) { activity ->
            Column(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 5.dp)
                    .clip(RoundedCornerShape(20.dp)).background(Surface)
                    .border(1.dp, Line.copy(alpha = .75f), RoundedCornerShape(20.dp))
                    .padding(15.dp)
                    .enterAnimation(enabled = !reduceMotion),
            ) {
                Row(verticalAlignment = Alignment.Top) {
                    Column(Modifier.weight(1f)) {
                        Text(activity.title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                        Spacer(Modifier.height(5.dp))
                        Text(activity.organizer, color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Medium)
                    }
                    IconButton(onClick = { onFavorite(activity.id) }, modifier = Modifier.size(36.dp)) {
                        Icon(
                            if (activity.isFavorite) Icons.Default.Bookmark else Icons.Default.BookmarkBorder,
                            null,
                            tint = if (activity.isFavorite) Accent else Muted,
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                MetaLine(Icons.Default.Schedule, activity.date)
                Spacer(Modifier.height(6.dp))
                MetaLine(Icons.Default.LocationOn, activity.location)
                Spacer(Modifier.height(13.dp))
                Button(
                    onClick = { onJoin(activity.id) },
                    modifier = Modifier.fillMaxWidth().height(42.dp),
                    shape = RoundedCornerShape(13.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (activity.status == "已报名") PrimarySoft else Primary,
                        contentColor = if (activity.status == "已报名") Primary else MaterialTheme.colorScheme.onPrimary,
                    ),
                ) {
                    Icon(
                        if (activity.status == "已报名") Icons.Default.CheckCircle else Icons.Default.AddCircleOutline,
                        null,
                        modifier = Modifier.size(17.dp),
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(if (activity.status == "已报名") "已报名 · 点击取消" else "报名活动", fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}

@Composable
private fun FavoriteList(
    favorites: List<FavoriteItem>,
    reduceMotion: Boolean,
    onOpen: (FavoriteItem) -> Unit,
    onRemove: (String) -> Unit,
) {
    ContentList(
        empty = favorites.isEmpty(),
        emptyIcon = Icons.Default.Bookmarks,
        emptyTitle = "还没有收藏",
        emptyHint = "收藏常用文件和活动，之后会更好找",
    ) {
        items(favorites, key = { it.id }) { favorite ->
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 5.dp)
                    .clip(RoundedCornerShape(18.dp)).background(Surface)
                    .campusClickable { onOpen(favorite) }
                    .padding(start = 14.dp, top = 13.dp, bottom = 13.dp, end = 5.dp)
                    .enterAnimation(enabled = !reduceMotion),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    Modifier.size(43.dp).clip(CircleShape).background(PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(favoriteIcon(favorite.type), null, tint = Primary, modifier = Modifier.size(21.dp))
                }
                Column(Modifier.padding(start = 12.dp).weight(1f)) {
                    Text(
                        favorite.title,
                        color = TextPrimary,
                        fontWeight = FontWeight.SemiBold,
                        fontSize = 14.sp,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(favorite.subtitle, color = Muted, fontSize = 11.sp, maxLines = 1)
                    Text("${favorite.type} · 收藏于 ${favorite.savedAt}", color = Muted.copy(alpha = .8f), fontSize = 10.sp)
                }
                IconButton(onClick = { onRemove(favorite.id) }) {
                    Icon(Icons.Default.BookmarkRemove, "取消收藏", tint = Accent)
                }
            }
        }
    }
}

@Composable
private fun ContentList(
    empty: Boolean,
    emptyIcon: ImageVector,
    emptyTitle: String,
    emptyHint: String,
    content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit,
) {
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(top = 6.dp, bottom = 92.dp),
    ) {
        if (empty) {
            item {
                Column(
                    Modifier.fillParentMaxSize().padding(bottom = 80.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Box(
                        Modifier.size(64.dp).clip(CircleShape).background(PrimarySoft),
                        contentAlignment = Alignment.Center,
                    ) { Icon(emptyIcon, null, tint = Primary, modifier = Modifier.size(30.dp)) }
                    Spacer(Modifier.height(14.dp))
                    Text(emptyTitle, color = TextPrimary, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(5.dp))
                    Text(emptyHint, color = Muted, fontSize = 12.sp)
                }
            }
        } else {
            content()
        }
    }
}

@Composable
private fun MetaLine(icon: ImageVector, text: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Icon(icon, null, tint = Muted, modifier = Modifier.size(16.dp))
        Spacer(Modifier.width(7.dp))
        Text(text, color = Muted, fontSize = 12.sp)
    }
}

private fun fileIcon(name: String): ImageVector = when {
    name.endsWith(".pdf", ignoreCase = true) -> Icons.Default.PictureAsPdf
    name.endsWith(".docx", ignoreCase = true) -> Icons.Default.Article
    else -> Icons.Default.InsertDriveFile
}

private fun favoriteIcon(type: String): ImageVector = when (type) {
    "文件" -> Icons.Default.Description
    "活动" -> Icons.Default.EventAvailable
    else -> Icons.Default.Notifications
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AddFileSheet(onDismiss: () -> Unit, onAdd: (String, String) -> Unit) {
    var name by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("课程资料") }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        containerColor = Surface,
        shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp),
    ) {
        Column(
            Modifier.fillMaxWidth().padding(start = 20.dp, end = 20.dp, bottom = 32.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Text("添加文件记录", color = TextPrimary, fontSize = 21.sp, fontWeight = FontWeight.Bold)
            Text("当前保存文件索引，不会上传真实文件内容。", color = Muted, fontSize = 12.sp)
            OutlinedTextField(
                value = name,
                onValueChange = { name = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("文件名") },
                placeholder = { Text("例如：操作系统实验报告.pdf") },
                leadingIcon = { Icon(Icons.Default.Description, null) },
                singleLine = true,
                shape = RoundedCornerShape(14.dp),
            )
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                listOf("课程资料", "校园事务", "竞赛资料").forEachIndexed { index, item ->
                    SegmentedButton(
                        selected = category == item,
                        onClick = { category = item },
                        shape = SegmentedButtonDefaults.itemShape(index, 3),
                    ) { Text(item, fontSize = 11.sp) }
                }
            }
            Button(
                onClick = { onAdd(name, category) },
                enabled = name.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(48.dp),
                shape = RoundedCornerShape(14.dp),
            ) {
                Text("保存到当前账号", fontWeight = FontWeight.Bold)
            }
        }
    }
}
