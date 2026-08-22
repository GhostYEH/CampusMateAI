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
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.launch

private val PanelShape = RoundedCornerShape(22.dp)

/**
 * 「我的大学」服务页。
 *
 * 功能边界：仅展示当前所属大学信息 + 校园服务入口（社区 / 热搜 / 教务 / 通知 / 待办），
 * **不提供**修改当前大学的入口。修改大学唯一入口在：
 * 我的 → 个人资料 → 编辑资料 → 所在大学（[com.example.campusai.ui.screens.profile.UniversityPickerScreen]）。
 *
 * 若用户尚未选择大学，引导其前往个人资料编辑页，而不是在此页内选择。
 */
@Composable
fun UniversityScreen(
    repository: AppRepository,
    onNavigate: (String) -> Unit,
) {
    val user by repository.session.collectAsState()
    val universityName = user?.universityName.orEmpty()
    val universityId = user?.universityId.orEmpty()
    val hasUniversity = universityId.isNotBlank()

    V3Page("我的大学", "当前学校信息、校园服务与一站式入口。") {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
                Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(46.dp).background(PrimarySoft, RoundedCornerShape(15.dp)), contentAlignment = Alignment.Center) {
                            Icon(Icons.Default.School, null, tint = Primary)
                        }
                        Column(Modifier.padding(start = 14.dp).weight(1f)) {
                            Text("当前所在大学", color = Muted, fontSize = 12.sp)
                            Text(
                                if (hasUniversity) universityName else "尚未选择大学",
                                color = TextPrimary,
                                fontSize = 18.sp,
                                fontWeight = FontWeight.Bold,
                            )
                        }
                    }
                    if (hasUniversity) {
                        Text(
                            "如需更换学校，请前往「我的 → 编辑资料 → 所在大学」修改。",
                            color = Muted,
                            fontSize = 12.sp,
                        )
                    } else {
                        Text("选择所在大学后，社区、失物招领与教务能力将按大学隔离。", color = Muted, fontSize = 12.sp)
                        Button(
                            onClick = { onNavigate("account") },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                        ) {
                            Icon(Icons.Default.Edit, null, modifier = Modifier.size(16.dp))
                            Spacer(Modifier.width(6.dp))
                            Text("去编辑资料选择大学")
                        }
                    }
                }
            }
        }
        if (hasUniversity) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("校园服务", color = TextPrimary, fontSize = 16.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 2.dp))
                    UniversityServiceList(universityServiceRows(onNavigate))
                }
            }
        }
    }
}

private fun universityServiceRows(onNavigate: (String) -> Unit): List<UniversityServiceRow> = listOf(
    UniversityServiceRow(Icons.Default.Groups, "校园社区", "当前大学的公开讨论与互助") { onNavigate("community") },
    UniversityServiceRow(Icons.Default.Whatshot, "校园热搜", "热门话题排行榜") { onNavigate("community_hot") },
    UniversityServiceRow(Icons.Default.AccountBalance, "教务系统", "课表、成绩与选课") { onNavigate("edu_system") },
    UniversityServiceRow(Icons.Default.NotificationsActive, "校园通知", "校园公告与提醒") { onNavigate("notifications") },
    UniversityServiceRow(Icons.Default.CheckCircle, "待办事项", "学习任务与截止") { onNavigate("tasks") },
)

private data class UniversityServiceRow(
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val title: String,
    val subtitle: String,
    val onClick: () -> Unit,
)

@Composable
private fun UniversityServiceList(rows: List<UniversityServiceRow>) {
    Card(colors = CardDefaults.cardColors(containerColor = Surface), shape = PanelShape) {
        Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
            rows.forEachIndexed { index, row ->
                Row(
                    Modifier.fillMaxWidth().padding(horizontal = 18.dp, vertical = 14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(40.dp).background(PrimarySoft, RoundedCornerShape(12.dp)), contentAlignment = Alignment.Center) {
                        Icon(row.icon, null, tint = Primary, modifier = Modifier.size(20.dp))
                    }
                    Column(Modifier.padding(start = 14.dp).weight(1f)) {
                        Text(row.title, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Medium)
                        Text(row.subtitle, color = Muted, fontSize = 12.sp)
                    }
                    Icon(Icons.Default.ChevronRight, null, tint = Muted, modifier = Modifier.size(20.dp))
                }
                if (index != rows.lastIndex) {
                    HorizontalDivider(color = Line, modifier = Modifier.padding(horizontal = 18.dp))
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
