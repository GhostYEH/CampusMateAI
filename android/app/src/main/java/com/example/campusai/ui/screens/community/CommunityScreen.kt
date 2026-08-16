package com.example.campusai.ui.screens.community

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.CommentDto
import com.example.campusai.data.remote.CommunityPostDto
import com.example.campusai.data.repository.CommunityRepository
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val CATEGORY_LABELS = mapOf(
    "question" to "提问", "recruit" to "招募", "errand" to "带价帮忙", "lostfound" to "失物招领",
    "campus" to "校园动态", "study" to "学习交流", "life" to "生活随笔", "secondhand" to "二手交易",
    "activity" to "活动", "experience" to "经验分享", "other" to "其它",
)

private fun fmtTime(iso: String): String {
    return try {
        val instant = Instant.parse(iso)
        instant.atZone(ZoneId.systemDefault()).format(DateTimeFormatter.ofPattern("MM-dd HH:mm"))
    } catch (_: Exception) { iso }
}

private fun catLabel(cat: String): String = CATEGORY_LABELS[cat] ?: cat

private fun extraTags(post: CommunityPostDto): List<String> {
    val e = post.extra ?: return emptyList()
    val tags = mutableListOf<String>()
    when (post.category) {
        "recruit" -> {
            (e["headcount"] as? Number)?.let { tags.add("招募 ${it} 人") }
            (e["location"] as? String)?.takeIf { it.isNotBlank() }?.let { tags.add("地点：$it") }
            (e["deadline"] as? String)?.takeIf { it.isNotBlank() }?.let { tags.add("截止：$it") }
        }
        "errand" -> {
            (e["price"] as? Number)?.let { tags.add("酬金 ¥$it") }
            (e["location"] as? String)?.takeIf { it.isNotBlank() }?.let { tags.add("地点：$it") }
            (e["deadline"] as? String)?.takeIf { it.isNotBlank() }?.let { tags.add("截止：$it") }
        }
        "lostfound" -> {
            tags.add(if (e["kind"] == "found") "招领" else "寻物")
            (e["location"] as? String)?.takeIf { it.isNotBlank() }?.let { tags.add("地点：$it") }
        }
    }
    return tags
}

@Composable
fun CommunityScreen(
    repository: CommunityRepository,
    onOpenDetail: (String) -> Unit,
    onOpenPublish: () -> Unit,
) {
    val posts by repository.posts.collectAsState()
    val loading by repository.loading.collectAsState()
    val error by repository.error.collectAsState()
    val categories by repository.categories.collectAsState()
    val total by repository.total.collectAsState()
    var query by remember { mutableStateOf("") }
    var selectedCategory by remember { mutableStateOf<String?>(null) }
    var sort by remember { mutableStateOf("time") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        repository.loadCategories()
        repository.refresh()
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text("校园论坛", color = TextPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                Text("提问 / 招募 / 带价帮忙 / 失物招领", color = Muted, fontSize = 12.sp)
            }
            Button(onClick = onOpenPublish, shape = RoundedCornerShape(12.dp)) {
                Icon(Icons.Default.Add, null); Spacer(Modifier.width(4.dp)); Text("发帖")
            }
        }

        Row(
            Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()).padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            FilterChip(selectedCategory == null, { selectedCategory = null; scope.launch { repository.refresh(query, null, sort) } }, label = { Text("全部") })
            categories.forEach { cat ->
                FilterChip(selectedCategory == cat.key, { selectedCategory = cat.key; scope.launch { repository.refresh(query, cat.key, sort) } }, label = { Text(cat.label) })
            }
        }

        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = query, onValueChange = { query = it },
                placeholder = { Text("搜索") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                modifier = Modifier.weight(1f),
                singleLine = true,
                shape = RoundedCornerShape(10.dp),
            )
            Row {
                FilterChip(sort == "time", { sort = "time"; scope.launch { repository.refresh(query, selectedCategory, "time") } }, label = { Text("最新") })
                Spacer(Modifier.width(4.dp))
                FilterChip(sort == "hot", { sort = "hot"; scope.launch { repository.refresh(query, selectedCategory, "hot") } }, label = { Text("热门") })
            }
        }

        if (error != null) {
            Text(error!!, color = DangerText, modifier = Modifier.padding(16.dp))
        }

        if (loading && posts.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else if (posts.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Text("暂无帖子，来发起第一场讨论吧", color = Muted)
            }
        } else {
            LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(posts, key = { it.id }) { post ->
                    CommunityPostCard(post, onOpenDetail = onOpenDetail, onLike = { scope.launch { repository.like(post.id) } }, onFavorite = { scope.launch { repository.favorite(post.id) } })
                }
                if (posts.size < total) {
                    item {
                        Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                            TextButton(onClick = { scope.launch { repository.loadMore() } }) { Text("加载更多") }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CommunityPostCard(post: CommunityPostDto, onOpenDetail: (String) -> Unit, onLike: () -> Unit, onFavorite: () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth().clickable { onOpenDetail(post.id) },
        colors = CardDefaults.cardColors(containerColor = Surface),
        shape = RoundedCornerShape(14.dp),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(36.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) {
                    Text(post.author_name.take(1), color = Primary, fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(post.author_name, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                    Text("${catLabel(post.category)} · ${fmtTime(post.created_at)}", color = Muted, fontSize = 11.sp)
                }
            }
            Text(post.title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 16.sp)
            Text(post.content, color = Muted, fontSize = 13.sp, maxLines = 4, overflow = TextOverflow.Ellipsis)
            if (post.images.isNotEmpty()) {
                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    post.images.forEach { img ->
                        AsyncImage(
                            model = ApiClient.resolveStaticUrl(img),
                            contentDescription = null,
                            modifier = Modifier.size(72.dp).clip(RoundedCornerShape(8.dp)),
                            contentScale = ContentScale.Crop,
                        )
                    }
                }
            }
            val tags = extraTags(post)
            if (tags.isNotEmpty()) {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    tags.forEach { tag ->
                        Text(tag, color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Medium,
                            modifier = Modifier.background(PrimarySoft, RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 3.dp))
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                TextButton(onClick = onLike) {
                    Icon(if (post.liked) Icons.Default.Favorite else Icons.Default.FavoriteBorder, null, tint = if (post.liked) Danger else Muted)
                    Text(" ${post.like_count}", color = if (post.liked) Danger else Muted)
                }
                TextButton(onClick = { onOpenDetail(post.id) }) {
                    Icon(Icons.Default.ChatBubbleOutline, null, tint = Muted)
                    Text(" ${post.comment_count}", color = Muted)
                }
                TextButton(onClick = onFavorite) {
                    Icon(if (post.favorited) Icons.Default.Bookmark else Icons.Default.BookmarkBorder, null, tint = if (post.favorited) Primary else Muted)
                    Text(" ${post.favorite_count}", color = if (post.favorited) Primary else Muted)
                }
            }
        }
    }
}

@Composable
fun CommunityDetailScreen(
    postId: String,
    repository: CommunityRepository,
    onBack: () -> Unit,
) {
    var post by remember { mutableStateOf<CommunityPostDto?>(null) }
    var comments by remember { mutableStateOf<List<CommentDto>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var commentText by remember { mutableStateOf("") }
    var replyTo by remember { mutableStateOf<CommentDto?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(postId) {
        loading = true; error = null
        val detailResult = repository.getDetail(postId)
        if (detailResult.isSuccess) {
            post = detailResult.getOrNull()
            comments = repository.listComments(postId)
        } else {
            error = detailResult.exceptionOrNull()?.message ?: "加载失败"
        }
        loading = false
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, null) }
            Text("帖子详情", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        if (loading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
        } else if (error != null) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { Text(error!!, color = DangerText) }
        } else if (post != null) {
            val p = post!!
            LazyColumn(Modifier.weight(1f).padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = RoundedCornerShape(14.dp)) {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(Modifier.size(38.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) {
                                    Text(p.author_name.take(1), color = Primary, fontWeight = FontWeight.Bold)
                                }
                                Spacer(Modifier.width(10.dp))
                                Column {
                                    Text(p.author_name, color = TextPrimary, fontWeight = FontWeight.SemiBold)
                                    Text("${catLabel(p.category)} · ${fmtTime(p.created_at)}", color = Muted, fontSize = 11.sp)
                                }
                            }
                            Text(p.title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                            Text(p.content, color = TextPrimary, fontSize = 14.sp, lineHeight = 22.sp)
                            if (p.images.isNotEmpty()) {
                                Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                    p.images.forEach { img ->
                                        AsyncImage(
                                            model = ApiClient.resolveStaticUrl(img),
                                            contentDescription = null,
                                            modifier = Modifier.size(160.dp).clip(RoundedCornerShape(10.dp)),
                                            contentScale = ContentScale.Crop,
                                        )
                                    }
                                }
                            }
                            val tags = extraTags(p)
                            if (tags.isNotEmpty()) {
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    tags.forEach { tag ->
                                        Text(tag, color = Primary, fontSize = 12.sp, fontWeight = FontWeight.Medium,
                                            modifier = Modifier.background(PrimarySoft, RoundedCornerShape(6.dp)).padding(horizontal = 8.dp, vertical = 3.dp))
                                    }
                                }
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                TextButton(onClick = { scope.launch { repository.likeWithState(p.id, p.liked).onSuccess { post = it } } }) {
                                    Icon(if (p.liked) Icons.Default.Favorite else Icons.Default.FavoriteBorder, null, tint = if (p.liked) Danger else Muted)
                                    Text(" ${p.like_count}", color = if (p.liked) Danger else Muted)
                                }
                                TextButton(onClick = { scope.launch { repository.favoriteWithState(p.id, p.favorited).onSuccess { post = it } } }) {
                                    Icon(if (p.favorited) Icons.Default.Bookmark else Icons.Default.BookmarkBorder, null, tint = if (p.favorited) Primary else Muted)
                                    Text(" ${p.favorite_count}", color = if (p.favorited) Primary else Muted)
                                }
                                if (p.is_owner) {
                                    TextButton(onClick = { scope.launch { if (repository.deletePost(p.id)) onBack() } }) {
                                        Icon(Icons.Default.Delete, null, tint = Danger); Text("删除", color = Danger)
                                    }
                                }
                            }
                        }
                    }
                }
                item { Text("评论 ${comments.size}", color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 15.sp, modifier = Modifier.padding(top = 8.dp)) }
                items(comments, key = { it.id }) { c ->
                    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = RoundedCornerShape(10.dp)) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(Modifier.size(28.dp).clip(CircleShape).background(PrimarySoft), contentAlignment = Alignment.Center) {
                                    Text(c.author_name.take(1), color = Primary, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                                }
                                Spacer(Modifier.width(8.dp))
                                Text(c.author_name, color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
                                Spacer(Modifier.weight(1f))
                                Text(fmtTime(c.created_at), color = Muted, fontSize = 10.sp)
                            }
                            Text(c.content, color = TextPrimary, fontSize = 13.sp, lineHeight = 20.sp)
                            TextButton(onClick = { replyTo = c; commentText = "@${c.author_name} " }) {
                                Text("回复", fontSize = 11.sp, color = Muted)
                            }
                        }
                    }
                }
            }
            Surface(color = Surface, tonalElevation = 4.dp) {
                Column(Modifier.padding(12.dp)) {
                    if (replyTo != null) {
                        Row(Modifier.fillMaxWidth().background(PrimarySoft, RoundedCornerShape(8.dp)).padding(8.dp), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("回复 @${replyTo!!.author_name}", color = Primary, fontSize = 12.sp)
                            IconButton(onClick = { replyTo = null; commentText = "" }, modifier = Modifier.size(20.dp)) { Icon(Icons.Default.Close, null, tint = Muted) }
                        }
                        Spacer(Modifier.height(4.dp))
                    }
                    OutlinedTextField(
                        value = commentText, onValueChange = { commentText = it },
                        placeholder = { Text("写下你的评论…") },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 2,
                        shape = RoundedCornerShape(10.dp),
                    )
                    Row(Modifier.fillMaxWidth().padding(top = 8.dp), horizontalArrangement = Arrangement.End) {
                        Button(
                            onClick = { scope.launch { repository.addComment(postId, com.example.campusai.data.remote.CommentCreateRequest(commentText.trim(), replyTo?.id)).onSuccess { comments = repository.listComments(postId); commentText = ""; replyTo = null } } },
                            enabled = commentText.isNotBlank(),
                        ) { Text("发送") }
                    }
                }
            }
        }
    }
}