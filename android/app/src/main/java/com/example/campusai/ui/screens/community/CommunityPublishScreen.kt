package com.example.campusai.ui.screens.community

import com.example.campusai.ui.components.GlassButton as Button
import com.example.campusai.ui.components.GlassCard as Card
import com.example.campusai.ui.components.GlassIconButton as IconButton
import com.example.campusai.ui.components.GlassOutlinedButton as OutlinedButton

import androidx.lifecycle.compose.collectAsStateWithLifecycle

import android.content.Context
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.AsyncImage
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.CommunityPostCreateRequest
import com.example.campusai.data.repository.CommunityRepository
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun CommunityPublishScreen(
    repository: CommunityRepository,
    onBack: () -> Unit,
    onPublished: (String) -> Unit,
) {
    val categories by repository.categories.collectAsStateWithLifecycle()
    var title by remember { mutableStateOf("") }
    var content by remember { mutableStateOf("") }
    var category by remember { mutableStateOf("campus") }
    var anonymous by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var sending by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val context = LocalContext.current

    val imageUrls = remember { mutableStateListOf<String>() }
    var uploadingImage by remember { mutableStateOf(false) }

    var extraHeadcount by remember { mutableStateOf("") }
    var extraLocation by remember { mutableStateOf("") }
    var extraDeadline by remember { mutableStateOf("") }
    var extraPrice by remember { mutableStateOf("") }
    var extraKind by remember { mutableStateOf("lost") }
    var extraContact by remember { mutableStateOf("") }
    var extraVisibility by remember { mutableStateOf("private") }

    LaunchedEffect(Unit) { if (categories.isEmpty()) repository.loadCategories() }

    val imagePicker = rememberLauncherForActivityResult(ActivityResultContracts.GetMultipleContents()) { uris ->
        if (uris.isEmpty()) return@rememberLauncherForActivityResult
        uploadingImage = true; error = null
        scope.launch {
            val uploadCount = uploadableCommunityImageCount(imageUrls.size, uris.size)
            for (uri in uris.take(uploadCount)) {
                val bytes = withContext(Dispatchers.IO) { readUriBytes(context, uri) }
                if (bytes == null) { error = "无法读取图片"; continue }
                val result = repository.uploadImage(bytes, "image.jpg")
                result.onSuccess { imageUrls.add(it.url) }.onFailure { error = it.message ?: "图片上传失败" }
            }
            uploadingImage = false
        }
    }

    fun buildExtra(): Map<String, Any?>? {
        return when (category) {
            "recruit" -> {
                val e = mutableMapOf<String, Any?>()
                extraHeadcount.toIntOrNull()?.let { e["headcount"] = it }
                if (extraLocation.isNotBlank()) e["location"] = extraLocation
                if (extraDeadline.isNotBlank()) e["deadline"] = extraDeadline
                if (e.isEmpty()) null else e
            }
            "errand" -> {
                val e = mutableMapOf<String, Any?>()
                extraPrice.toDoubleOrNull()?.let { e["price"] = it }
                if (extraLocation.isNotBlank()) e["location"] = extraLocation
                if (extraDeadline.isNotBlank()) e["deadline"] = extraDeadline
                if (e.isEmpty()) null else e
            }
            else -> null
        }
    }

    Column(Modifier.fillMaxSize().background(Background)) {
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = onBack) { Icon(Icons.Default.ArrowBack, null) }
            Text("发布帖子", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }
        Column(Modifier.fillMaxSize().padding(horizontal = 16.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Card(colors = CardDefaults.cardColors(containerColor = PrimarySoft), shape = RoundedCornerShape(18.dp)) {
                Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) { Icon(Icons.Default.Campaign, null, tint = Primary); Spacer(Modifier.width(10.dp)); Text("分享校园信息，友善交流，注意保护隐私", color = TextPrimary, fontSize = 13.sp) }
            }
            OutlinedTextField(title, { title = it.take(60) }, label = { Text("● 标题   ${title.length}/60") }, placeholder = { Text("输入一个清晰的标题") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(18.dp))
            OutlinedTextField(content, { content = it.take(1000) }, label = { Text("● 正文   ${content.length}/1000") }, placeholder = { Text("写下你的内容、问题或需求…") }, modifier = Modifier.fillMaxWidth(), minLines = 7, shape = RoundedCornerShape(18.dp))

            Text("● 选择分类", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                categories.take(6).forEach { cat ->
                    FilterChip(category == cat.key, { category = cat.key }, label = { Text(cat.label) })
                }
            }
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                categories.drop(6).forEach { cat ->
                    FilterChip(category == cat.key, { category = cat.key }, label = { Text(cat.label) })
                }
            }

            Text("● 添加图片（最多9张）", color = TextPrimary, fontWeight = FontWeight.SemiBold, fontSize = 17.sp)
            Row(Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                imageUrls.forEach { url ->
                    Box {
                        AsyncImage(
                            model = ApiClient.resolveStaticUrl(url),
                            contentDescription = null,
                            modifier = Modifier.size(80.dp).clip(RoundedCornerShape(8.dp)),
                            contentScale = ContentScale.Crop,
                        )
                        IconButton(
                            onClick = { imageUrls.remove(url) },
                            modifier = Modifier.size(24.dp).align(Alignment.TopEnd).clip(CircleShape).background(Surface),
                        ) { Icon(Icons.Default.Close, null, tint = Danger, modifier = Modifier.size(14.dp)) }
                    }
                }
                if (imageUrls.size < 9) {
                    OutlinedButton(onClick = { imagePicker.launch("image/*") }, enabled = !uploadingImage, modifier = Modifier.size(80.dp)) {
                        if (uploadingImage) CircularProgressIndicator(modifier = Modifier.size(20.dp), strokeWidth = 2.dp)
                        else Icon(Icons.Default.AddPhotoAlternate, null)
                    }
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(anonymous, { anonymous = it })
                Text("校园匿名", color = Muted, fontSize = 13.sp)
            }

            if (category == "recruit") {
                ExtraSection("招募信息") {
                    OutlinedTextField(extraHeadcount, { extraHeadcount = it }, label = { Text("招募人数") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                    OutlinedTextField(extraLocation, { extraLocation = it }, label = { Text("地点") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                    OutlinedTextField(extraDeadline, { extraDeadline = it }, label = { Text("截止时间") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                }
            }
            if (category == "errand") {
                ExtraSection("帮忙信息") {
                    OutlinedTextField(extraPrice, { extraPrice = it }, label = { Text("酬金（元）") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                    OutlinedTextField(extraLocation, { extraLocation = it }, label = { Text("地点") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                    OutlinedTextField(extraDeadline, { extraDeadline = it }, label = { Text("截止时间") }, modifier = Modifier.fillMaxWidth(), singleLine = true, shape = RoundedCornerShape(10.dp))
                }
            }

            if (error != null) Text(error!!, color = DangerText, fontSize = 13.sp)

            Button(
                onClick = {
                    if (title.isBlank() || content.isBlank()) { error = "标题和正文不能为空"; return@Button }
                    sending = true; error = null
                    scope.launch {
                        val result = repository.publish(CommunityPostCreateRequest(title.trim(), content.trim(), category, images = imageUrls.toList(), is_anonymous = anonymous, extra = buildExtra()))
                        sending = false
                        result.onSuccess { onPublished(it.id) }.onFailure { error = it.message ?: "发布失败" }
                    }
                },
                modifier = Modifier.fillMaxWidth(),
                enabled = !sending,
                shape = RoundedCornerShape(12.dp),
            ) { Text(if (sending) "发布中…" else "确认发布") }
            Spacer(Modifier.height(24.dp))
        }
    }
}

internal fun uploadableCommunityImageCount(currentCount: Int, pickedCount: Int): Int {
    return minOf((9 - currentCount).coerceAtLeast(0), pickedCount.coerceAtLeast(0))
}

private fun readUriBytes(context: Context, uri: Uri): ByteArray? {
    return try {
        context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
    } catch (_: Exception) { null }
}

@Composable
private fun ExtraSection(title: String, content: @Composable ColumnScope.() -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = PrimarySoft), shape = RoundedCornerShape(12.dp)) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(title, color = Primary, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
            content()
        }
    }
}
