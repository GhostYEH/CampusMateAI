package com.example.campusai.ui.screens.v3

import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.remote.*
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private val PanelShape = RoundedCornerShape(22.dp)

@Composable
fun UniversityScreen() {
    var query by remember { mutableStateOf("") }
    var universities by remember { mutableStateOf(emptyList<UniversityDto>()) }
    var selectedId by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        loading = true
        message = null
        runCatching {
            val me = ApiClient.api.me()
            if (me.isSuccessful) selectedId = me.body()?.user?.university_id
            val response = ApiClient.api.listUniversities(query.takeIf(String::isNotBlank))
            check(response.isSuccessful) { "大学列表加载失败 (${response.code()})" }
            universities = response.body()?.items.orEmpty()
        }.onFailure { message = it.message ?: "大学列表加载失败" }
        loading = false
    }
    LaunchedEffect(Unit) { load() }

    V3Page("我的大学", "选择后，社区、失物招领和教务能力将按大学隔离。") {
        item {
            OutlinedTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("搜索大学") },
                leadingIcon = { Icon(Icons.Default.Search, null) },
                trailingIcon = { IconButton(onClick = { scope.launch { load() } }) { Icon(Icons.Default.ArrowForward, "搜索") } },
                singleLine = true,
                shape = RoundedCornerShape(18.dp),
            )
        }
        statusItems(loading, message, universities.isEmpty(), "未找到匹配的大学")
        items(universities, key = { it.id }) { university ->
            Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
                Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(46.dp).background(PrimarySoft, RoundedCornerShape(15.dp)), contentAlignment = Alignment.Center) {
                        Icon(Icons.Default.School, null, tint = Primary)
                    }
                    Column(Modifier.padding(start = 14.dp).weight(1f)) {
                        Text(university.name, color = TextPrimary, fontWeight = FontWeight.Bold)
                        Text(listOfNotNull(university.province, university.city).joinToString(" · ").ifBlank { "中国" }, color = Muted, fontSize = 12.sp)
                        Text(if (university.academic_provider == "unsupported") "暂未支持自动教务同步" else "支持教务同步", color = Muted, fontSize = 11.sp)
                    }
                    if (selectedId == university.id) {
                        AssistChip(onClick = {}, label = { Text("当前大学") }, leadingIcon = { Icon(Icons.Default.CheckCircle, null, Modifier.size(16.dp)) })
                    } else {
                        Button(onClick = {
                            scope.launch {
                                val response = ApiClient.api.selectUniversity(UniversitySelectionRequest(university.id))
                                if (response.isSuccessful) {
                                    selectedId = university.id
                                    message = "已切换到 ${university.name}，大学范围数据已更新"
                                } else message = "切换大学失败 (${response.code()})"
                            }
                        }) { Text("选择") }
                    }
                }
            }
        }
    }
}

@Composable
fun CommunityScreen() {
    var posts by remember { mutableStateOf(emptyList<CommunityPostDto>()) }
    var loading by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var composing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    suspend fun load() {
        loading = true
        val response = runCatching { ApiClient.api.listCommunityPosts() }.getOrNull()
        if (response?.isSuccessful == true) {
            posts = response.body()?.items.orEmpty(); message = null
        } else message = if (response?.code() == 409) "请先在“我的大学”中选择学校" else "社区加载失败"
        loading = false
    }
    LaunchedEffect(Unit) { load() }

    V3Page("校园社区", "只展示当前大学的公开讨论与同学互助。") {
        item {
            Button(onClick = { composing = true }, modifier = Modifier.fillMaxWidth(), shape = RoundedCornerShape(16.dp)) {
                Icon(Icons.Default.Add, null); Spacer(Modifier.width(8.dp)); Text("发布帖子")
            }
        }
        statusItems(loading, message, posts.isEmpty(), "暂无帖子，来发起第一场校园讨论吧")
        items(posts, key = { it.id }) { post ->
            Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
                Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(34.dp).background(PrimarySoft, CircleShape), contentAlignment = Alignment.Center) {
                            Text(post.author_name.take(1), color = Primary, fontWeight = FontWeight.Bold)
                        }
                        Column(Modifier.padding(start = 10.dp).weight(1f)) {
                            Text(post.author_name, color = TextPrimary, fontWeight = FontWeight.SemiBold)
                            Text(post.category, color = Muted, fontSize = 11.sp)
                        }
                    }
                    Text(post.title, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                    Text(post.content, color = Muted, lineHeight = 21.sp)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TextButton(onClick = { scope.launch { ApiClient.api.likeCommunityPost(post.id).body()?.let { changed -> posts = posts.map { if (it.id == changed.id) changed else it } } } }) { Icon(Icons.Default.FavoriteBorder, null); Text(" ${post.like_count}") }
                        TextButton(onClick = {}) { Icon(Icons.Default.ChatBubbleOutline, null); Text(" ${post.comment_count}") }
                        TextButton(onClick = { scope.launch { ApiClient.api.favoriteCommunityPost(post.id).body()?.let { changed -> posts = posts.map { if (it.id == changed.id) changed else it } } } }) { Icon(Icons.Default.BookmarkBorder, null); Text(" ${post.favorite_count}") }
                    }
                }
            }
        }
    }
    if (composing) CommunityComposer(
        onDismiss = { composing = false },
        onPublish = { request -> scope.launch {
            val response = ApiClient.api.createCommunityPost(request)
            if (response.isSuccessful) { composing = false; load() } else message = "发布失败 (${response.code()})"
        } },
    )
}

@Composable
private fun CommunityComposer(onDismiss: () -> Unit, onPublish: (CommunityPostCreateRequest) -> Unit) {
    var title by remember { mutableStateOf("") }; var content by remember { mutableStateOf("") }; var anonymous by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("发布帖子") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedTextField(title, { title = it.take(120) }, label = { Text("标题") }, singleLine = true)
            OutlinedTextField(content, { content = it.take(10000) }, label = { Text("正文") }, minLines = 4)
            Row(verticalAlignment = Alignment.CenterVertically) { Checkbox(anonymous, { anonymous = it }); Text("校园匿名") }
        } },
        confirmButton = { Button(enabled = title.isNotBlank() && content.isNotBlank(), onClick = { onPublish(CommunityPostCreateRequest(title.trim(), content.trim(), is_anonymous = anonymous)) }) { Text("确认发布") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@Composable
fun AcademicScreen() {
    var status by remember { mutableStateOf(AcademicStatusDto("unsupported", "unsupported")) }
    var message by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        val response = runCatching { ApiClient.api.academicStatus() }.getOrNull()
        if (response?.isSuccessful == true) status = response.body() ?: status
        else message = if (response?.code() == 409) "请先选择你的大学" else "教务状态加载失败"
    }
    V3Page("教务系统", "连接学生自己的教务账号，同步课程、课表、成绩和考试。") {
        message?.let { item { V3Message(it) } }
        item {
            Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
                Row(Modifier.fillMaxWidth().padding(20.dp), verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(52.dp).background(PrimarySoft, RoundedCornerShape(17.dp)), contentAlignment = Alignment.Center) { Icon(Icons.Default.School, null, tint = Primary) }
                    Column(Modifier.padding(start = 16.dp)) {
                        Text("当前连接状态", color = Muted, fontSize = 12.sp)
                        Text(if (status.status == "unsupported") "暂未支持自动教务同步" else status.status, color = TextPrimary, fontWeight = FontWeight.Bold, fontSize = 18.sp)
                        Text("Provider: ${status.provider}", color = Muted, fontSize = 12.sp)
                    }
                }
            }
        }
        item {
            Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFF2F0FF)), shape = PanelShape) {
                Row(Modifier.padding(18.dp), verticalAlignment = Alignment.Top) {
                    Icon(Icons.Default.Shield, null, tint = Primary)
                    Column(Modifier.padding(start = 12.dp)) {
                        Text("凭证安全", color = TextPrimary, fontWeight = FontWeight.Bold)
                        Text("教务密码仅通过 HTTPS 发送到 Backend 完成认证，不会保存在本机、API 响应或日志中。未验证的学校不会显示假绑定或假课程。", color = Muted, fontSize = 13.sp, lineHeight = 20.sp)
                    }
                }
            }
        }
    }
}

@Composable
private fun V3Page(title: String, subtitle: String, content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit) {
    LazyColumn(
        Modifier.fillMaxSize().background(Background),
        contentPadding = PaddingValues(18.dp, 18.dp, 18.dp, 110.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { Column { Text(title, color = TextPrimary, fontSize = 28.sp, fontWeight = FontWeight.Bold); Spacer(Modifier.height(5.dp)); Text(subtitle, color = Muted, fontSize = 13.sp) } }
        content()
    }
}

private fun androidx.compose.foundation.lazy.LazyListScope.statusItems(loading: Boolean, message: String?, empty: Boolean, emptyText: String) {
    if (loading) item { LinearProgressIndicator(Modifier.fillMaxWidth()) }
    message?.let { item { V3Message(it) } }
    if (!loading && empty) item { V3Message(emptyText) }
}

@Composable
private fun V3Message(text: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
        Row(Modifier.fillMaxWidth().padding(18.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Info, null, tint = Primary); Text(text, Modifier.padding(start = 10.dp), color = Muted)
        }
    }
}
