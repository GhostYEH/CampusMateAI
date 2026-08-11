package com.example.campusai.ui.screens.notifications

import androidx.compose.foundation.background
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.FavoriteBorder
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.news.NewsFeedItem
import com.example.campusai.data.news.NewsFeedQuery
import com.example.campusai.data.news.NewsSort
import com.example.campusai.data.news.buildCampusNewsFeed
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.CampusCard
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.ErrorState
import com.example.campusai.ui.components.FilterChipRow
import com.example.campusai.ui.components.LoadingState
import com.example.campusai.ui.components.PageEmptyState
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

private const val AllCategories = "全部"

@Composable
fun CampusNewsScreen(
    repository: AppRepository,
    onBack: () -> Unit,
    onOpenNews: (String) -> Unit,
) {
    var keyword by rememberSaveable { mutableStateOf("") }
    var category by rememberSaveable { mutableStateOf(AllCategories) }
    var unreadOnly by rememberSaveable { mutableStateOf(false) }
    var sortName by rememberSaveable { mutableStateOf(NewsSort.LATEST.name) }
    var isRefreshing by rememberSaveable { mutableStateOf(false) }
    var refreshError by rememberSaveable { mutableStateOf<String?>(null) }

    val news by repository.campusNews.collectAsState()
    val readIds by repository.newsReadIds.collectAsState()
    val favoriteIds by repository.newsFavoriteIds.collectAsState()
    val scope = rememberCoroutineScope()
    val sort = NewsSort.valueOf(sortName)
    val categories = listOf(AllCategories) + news.map { it.category.trim() }
        .filter { it.isNotBlank() }
        .distinct()
    val results = buildCampusNewsFeed(
        items = news,
        query = NewsFeedQuery(keyword, category, unreadOnly, sort),
        readIds = readIds,
        favoriteIds = favoriteIds,
    )

    fun refresh() {
        scope.launch {
            isRefreshing = true
            refreshError = null
            try {
                if (!repository.refreshCampusNews()) {
                    refreshError = "刷新失败，请稍后重试"
                }
            } catch (_: Exception) {
                refreshError = "刷新失败，请稍后重试"
            } finally {
                isRefreshing = false
            }
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(16.dp))
        CampusPageHeader(
            title = "校园动态",
            subtitle = "${results.size} 条结果",
            onBack = onBack,
            actions = {
                IconButton(onClick = ::refresh, enabled = !isRefreshing) {
                    Icon(Icons.Default.Refresh, "刷新", tint = Primary)
                }
            },
        )
        Spacer(Modifier.height(16.dp))
        OutlinedTextField(
            value = keyword,
            onValueChange = { keyword = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            leadingIcon = { Icon(Icons.Default.Search, null, tint = Muted) },
            placeholder = { Text("搜索标题、来源或分类", color = Muted) },
            shape = RoundedCornerShape(18.dp),
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = Primary,
                unfocusedBorderColor = Line,
                focusedTextColor = TextPrimary,
                unfocusedTextColor = TextPrimary,
                cursorColor = Primary,
            ),
        )
        Spacer(Modifier.height(12.dp))
        FilterChipRow(options = categories, selected = category, onSelect = { category = it })
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NewsControl("最新", sort == NewsSort.LATEST) { sortName = NewsSort.LATEST.name }
            NewsControl("重要", sort == NewsSort.IMPORTANT) { sortName = NewsSort.IMPORTANT.name }
            Spacer(Modifier.weight(1f))
            NewsControl(
                label = if (unreadOnly) "仅未读" else "全部",
                selected = unreadOnly,
                icon = if (unreadOnly) Icons.Default.VisibilityOff else Icons.Default.Visibility,
            ) { unreadOnly = !unreadOnly }
        }
        Spacer(Modifier.height(12.dp))

        when {
            news.isEmpty() && isRefreshing -> LoadingState("正在加载校园动态", Modifier.weight(1f))
            news.isEmpty() && refreshError != null -> ErrorState(
                message = refreshError.orEmpty(),
                onRetry = ::refresh,
                modifier = Modifier.weight(1f),
            )
            news.isEmpty() -> PageEmptyState(Icons.Default.Search, "暂时没有校园动态", Modifier.weight(1f))
            results.isEmpty() -> Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                if (refreshError != null) {
                    RefreshErrorNotice(message = refreshError.orEmpty(), onRetry = ::refresh)
                }
                PageEmptyState(
                    icon = Icons.Default.Search,
                    message = "没有匹配的校园动态",
                    modifier = Modifier.weight(1f),
                )
            }
            else -> LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(
                    bottom = BottomDockReservedHeight +
                        WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding(),
                ),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Text("共 ${results.size} 条动态", color = Muted, fontSize = 12.sp)
                }
                if (refreshError != null) {
                    item {
                        RefreshErrorNotice(message = refreshError.orEmpty(), onRetry = ::refresh)
                    }
                }
                val featuredItem = results.first()
                item(key = featuredItem.news.id) {
                    FeaturedNewsCard(
                        item = featuredItem,
                        onOpen = {
                            scope.launch {
                                repository.markCampusNewsRead(featuredItem.news.id)
                                onOpenNews(featuredItem.news.id)
                            }
                        },
                        onFavorite = {
                            scope.launch { repository.toggleCampusNewsFavorite(featuredItem.news.id) }
                        },
                    )
                }
                items(results.drop(1), key = { it.news.id }) { item ->
                    CompactNewsCard(
                        item = item,
                        onOpen = {
                            scope.launch {
                                repository.markCampusNewsRead(item.news.id)
                                onOpenNews(item.news.id)
                            }
                        },
                        onFavorite = { scope.launch { repository.toggleCampusNewsFavorite(item.news.id) } },
                    )
                }
            }
        }
    }
}

@Composable
private fun NewsControl(
    label: String,
    selected: Boolean,
    icon: androidx.compose.ui.graphics.vector.ImageVector? = null,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .background(if (selected) PrimarySoft else Surface)
            .campusClickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = if (selected) Primary else Muted, modifier = Modifier.size(15.dp))
            Spacer(Modifier.width(4.dp))
        }
        Text(label, color = if (selected) Primary else Muted, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun FeaturedNewsCard(item: NewsFeedItem, onOpen: () -> Unit, onFavorite: () -> Unit) {
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onOpen),
        padding = androidx.compose.foundation.layout.PaddingValues(18.dp),
    ) {
        NewsMeta(item, onFavorite)
        Spacer(Modifier.height(10.dp))
        Text(item.news.title, color = TextPrimary, fontSize = 19.sp, fontWeight = FontWeight.Bold, maxLines = 2, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(8.dp))
        Text(item.news.summary, color = Muted, fontSize = 13.sp, maxLines = 3, overflow = TextOverflow.Ellipsis)
        Spacer(Modifier.height(12.dp))
        Text("${item.news.source} · ${item.news.time}", color = Muted, fontSize = 11.sp)
    }
}

@Composable
private fun CompactNewsCard(item: NewsFeedItem, onOpen: () -> Unit, onFavorite: () -> Unit) {
    CampusCard(
        modifier = Modifier.campusClickable(onClick = onOpen),
        padding = androidx.compose.foundation.layout.PaddingValues(16.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                NewsMeta(item, onFavorite)
                Spacer(Modifier.height(7.dp))
                Text(item.news.title, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(5.dp))
                Text(item.news.summary, color = Muted, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Spacer(Modifier.height(9.dp))
                Text("${item.news.source} · ${item.news.time}", color = Muted, fontSize = 10.5.sp)
            }
        }
    }
}

@Composable
private fun NewsMeta(item: NewsFeedItem, onFavorite: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(item.news.category, color = Primary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
        Spacer(Modifier.width(8.dp))
        Text(if (item.isRead) "已读" else "未读", color = if (item.isRead) Muted else Primary, fontSize = 11.sp)
        Spacer(Modifier.weight(1f))
        IconButton(onClick = onFavorite, modifier = Modifier.size(30.dp)) {
            Icon(
                if (item.isFavorite) Icons.Default.Favorite else Icons.Default.FavoriteBorder,
                contentDescription = if (item.isFavorite) "取消收藏" else "收藏",
                tint = if (item.isFavorite) Primary else Muted,
                modifier = Modifier.size(18.dp),
            )
        }
    }
}

@Composable
private fun RefreshErrorNotice(message: String, onRetry: () -> Unit) {
    CampusCard(padding = androidx.compose.foundation.layout.PaddingValues(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(message, color = Muted, fontSize = 12.sp, modifier = Modifier.weight(1f))
            Text(
                "重试",
                color = Primary,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.campusClickable(onClick = onRetry).padding(8.dp),
            )
        }
    }
}
