package com.example.campusai.ui.screens.profile

import android.Manifest
import android.content.pm.PackageManager
import android.graphics.BitmapFactory
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.CloudUpload
import androidx.compose.material.icons.filled.DeleteOutline
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.campusai.data.model.ExpressionLabel
import com.example.campusai.data.repository.AppRepository
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.theme.AlertErrorBg
import com.example.campusai.ui.theme.AlertErrorText
import com.example.campusai.ui.theme.AlertInfoBg
import com.example.campusai.ui.theme.AlertInfoText
import com.example.campusai.ui.theme.Danger
import com.example.campusai.ui.theme.Success
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun ExpressionContributionScreen(
    repository: AppRepository,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()
    val reduceMotion by repository.reduceMotion.collectAsStateWithLifecycle()
    val mockMode by repository.mockMode.collectAsStateWithLifecycle()
    val backendOnline by repository.backendOnline.collectAsStateWithLifecycle()

    var consentGiven by remember { mutableStateOf(false) }
    var permissionGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED,
        )
    }
    var permissionDenied by remember { mutableStateOf(false) }
    var previewFile by remember { mutableStateOf<File?>(null) }
    var selectedLabel by remember { mutableStateOf<ExpressionLabel?>(null) }
    var imageCapture by remember { mutableStateOf<ImageCapture?>(null) }
    var cameraProvider by remember { mutableStateOf<ProcessCameraProvider?>(null) }
    var capturing by remember { mutableStateOf(false) }
    var uploading by remember { mutableStateOf(false) }
    var uploadedSampleId by remember { mutableStateOf<String?>(null) }
    var uploadedCount by remember { mutableStateOf(0) }
    var statusMessage by remember { mutableStateOf<String?>(null) }
    var statusIsError by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        permissionGranted = granted
        permissionDenied = !granted
        if (!granted) {
            statusIsError = true
            statusMessage = "未获得相机权限，无法采集共建样本"
        }
    }

    fun discardLocalSample() {
        previewFile?.delete()
        previewFile = null
        selectedLabel = null
        capturing = false
    }

    fun bindCamera(previewView: PreviewView) {
        val future = ProcessCameraProvider.getInstance(context)
        future.addListener({
            try {
                val provider = future.get()
                val preview = Preview.Builder().build().also {
                    it.setSurfaceProvider(previewView.surfaceProvider)
                }
                val capture = ImageCapture.Builder()
                    .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY)
                    .build()
                provider.unbindAll()
                provider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_FRONT_CAMERA,
                    preview,
                    capture,
                )
                cameraProvider = provider
                imageCapture = capture
            } catch (_: Exception) {
                statusIsError = true
                statusMessage = "摄像头启动失败，请稍后重试"
            }
        }, ContextCompat.getMainExecutor(context))
    }

    fun captureSample() {
        val capture = imageCapture
        if (capture == null) {
            statusIsError = true
            statusMessage = "摄像头还在准备中，请稍等"
            return
        }
        val file = File(context.cacheDir, "expression_contribution_${System.currentTimeMillis()}.jpg")
        capturing = true
        val options = ImageCapture.OutputFileOptions.Builder(file).build()
        capture.takePicture(
            options,
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(outputFileResults: ImageCapture.OutputFileResults) {
                    previewFile = file
                    selectedLabel = null
                    capturing = false
                    statusIsError = false
                    statusMessage = "图片已暂存本机，请选择你认为符合的表情标签"
                }

                override fun onError(exception: ImageCaptureException) {
                    file.delete()
                    capturing = false
                    statusIsError = true
                    statusMessage = "图片采集失败，请重新尝试"
                }
            },
        )
    }

    DisposableEffect(consentGiven, previewFile, lifecycleOwner) {
        onDispose {
            cameraProvider?.unbindAll()
            imageCapture = null
            previewFile?.delete()
        }
    }

    Box(Modifier.fillMaxSize().background(ReferencePageBackground)) {
        Column(Modifier.fillMaxSize().navigationBarsPadding()) {
            LazyColumn(
                modifier = Modifier.weight(1f),
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 4.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp),
            ) {
                item {
                    ContributionIntro(uploadedCount = uploadedCount, reduceMotion = reduceMotion)
                }
                item {
                    ConsentCard(
                        checked = consentGiven,
                        onCheckedChange = {
                            consentGiven = it
                            if (!it) discardLocalSample()
                        },
                    )
                }
                item {
                    when {
                        !consentGiven -> ContributionLockedCard()
                        !permissionGranted -> PermissionCard(
                            denied = permissionDenied,
                            onRequest = { permissionLauncher.launch(Manifest.permission.CAMERA) },
                        )
                        previewFile == null -> CameraCaptureCard(
                            capturing = capturing,
                            onCapture = ::captureSample,
                            onBind = ::bindCamera,
                        )
                        else -> SampleReviewCard(
                            file = previewFile!!,
                            selectedLabel = selectedLabel,
                            uploading = uploading,
                            canUpload = !mockMode && backendOnline,
                            onSelectLabel = { selectedLabel = it },
                            onRetake = ::discardLocalSample,
                            onUpload = {
                                val file = previewFile ?: return@SampleReviewCard
                                val label = selectedLabel ?: return@SampleReviewCard
                                scope.launch {
                                    uploading = true
                                    statusMessage = null
                                    try {
                                        uploadedSampleId = repository.uploadExpressionContribution(file, label)
                                        uploadedCount += 1
                                        file.delete()
                                        previewFile = null
                                        selectedLabel = null
                                        statusIsError = false
                                        statusMessage = "样本已上传，感谢你的共建"
                                    } catch (error: Exception) {
                                        statusIsError = true
                                        statusMessage = error.message ?: "上传失败，请稍后重试"
                                    } finally {
                                        uploading = false
                                    }
                                }
                            },
                        )
                    }
                }
                uploadedSampleId?.let { sampleId ->
                    item {
                        UploadedSampleCard(
                            sampleId = sampleId,
                            deleting = uploading,
                            onDelete = {
                                scope.launch {
                                    uploading = true
                                    try {
                                        repository.deleteExpressionContribution(sampleId)
                                        uploadedSampleId = null
                                        uploadedCount = (uploadedCount - 1).coerceAtLeast(0)
                                        statusIsError = false
                                        statusMessage = "这条共建样本已从服务器删除"
                                    } catch (error: Exception) {
                                        statusIsError = true
                                        statusMessage = error.message ?: "删除失败，请稍后重试"
                                    } finally {
                                        uploading = false
                                    }
                                }
                            },
                        )
                    }
                }
                statusMessage?.let { message ->
                    item { StatusBanner(message = message, isError = statusIsError) }
                }
            }
        }
    }
}

@Composable
private fun ContributionIntro(uploadedCount: Int, reduceMotion: Boolean) {
    Column(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(22.dp))
            .background(ReferencePrimarySoft)
            .padding(18.dp)
            .enterAnimation(enabled = !reduceMotion),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.Lock, null, tint = ReferencePrimary, modifier = Modifier.size(20.dp))
            Spacer(Modifier.size(8.dp))
            Text("隐私优先的单帧共建", color = ReferenceText, fontSize = 16.sp, fontWeight = FontWeight.Bold)
        }
        Text(
            "每次只采集一张由你主动拍摄的图片。你负责确认标签，上传前可重新拍摄，上传后也可以删除自己的样本。",
            color = ReferenceMuted,
            fontSize = 11.sp,
            lineHeight = 17.sp,
        )
        Text("本次已上传 $uploadedCount 条", color = ReferencePrimary, fontSize = 11.sp, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun ConsentCard(checked: Boolean, onCheckedChange: (Boolean) -> Unit) {
    Surface(
        modifier = Modifier.fillMaxWidth().border(1.dp, ReferenceDivider, RoundedCornerShape(18.dp)),
        color = ReferenceSurface,
        shape = RoundedCornerShape(18.dp),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.Top) {
            Checkbox(checked = checked, onCheckedChange = onCheckedChange)
            Column(Modifier.padding(top = 9.dp, start = 4.dp)) {
                Text("我同意参与 CNN 表情模型共建", color = ReferenceText, fontSize = 13.sp, fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(4.dp))
                Text(
                    "我理解图片会上传到项目后端，用于人工复核、数据分析和后续模型训练；这不是心理诊断，也不代表我的心理状态。",
                    color = ReferenceMuted,
                    fontSize = 10.sp,
                    lineHeight = 15.sp,
                )
            }
        }
    }
}

@Composable
private fun ContributionLockedCard() {
    InfoCard(
        icon = Icons.Default.Lock,
        title = "开启同意后才能采集",
        text = "模型共建不会在后台自动打开摄像头，也不会在未同意时保存或上传图片。",
    )
}

@Composable
private fun PermissionCard(denied: Boolean, onRequest: () -> Unit) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(ReferenceSurface)
            .border(1.dp, ReferenceDivider, RoundedCornerShape(18.dp)).padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        InfoCard(
            Icons.Default.CameraAlt,
            "需要摄像头权限",
            if (denied) "权限未开启，请在系统设置中允许后重试。" else "只在你打开本页并主动拍摄时使用摄像头。",
        )
        Button(onClick = onRequest, colors = ButtonDefaults.buttonColors(containerColor = ReferencePrimary)) {
            Text("授权摄像头")
        }
    }
}

@Composable
private fun CameraCaptureCard(
    capturing: Boolean,
    onCapture: () -> Unit,
    onBind: (PreviewView) -> Unit,
) {
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(ReferenceSurface)
            .border(1.dp, ReferenceDivider, RoundedCornerShape(18.dp)).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("拍摄一张自然状态的正面照片", color = ReferenceText, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        AndroidView(
            factory = { cameraContext ->
                PreviewView(cameraContext).apply {
                    scaleType = PreviewView.ScaleType.FILL_CENTER
                    implementationMode = PreviewView.ImplementationMode.COMPATIBLE
                    onBind(this)
                }
            },
            modifier = Modifier.fillMaxWidth().height(230.dp).clip(RoundedCornerShape(14.dp)),
        )
        Button(
            onClick = onCapture,
            enabled = !capturing,
            modifier = Modifier.fillMaxWidth(),
            colors = ButtonDefaults.buttonColors(containerColor = ReferencePrimary),
        ) {
            if (capturing) {
                CircularProgressIndicator(Modifier.size(17.dp), strokeWidth = 2.dp, color = Color.White)
            } else {
                Icon(Icons.Default.CameraAlt, null, Modifier.size(17.dp))
            }
            Spacer(Modifier.size(7.dp))
            Text(if (capturing) "正在保存图片" else "拍摄并进入打标")
        }
    }
}

@Composable
private fun SampleReviewCard(
    file: File,
    selectedLabel: ExpressionLabel?,
    uploading: Boolean,
    canUpload: Boolean,
    onSelectLabel: (ExpressionLabel) -> Unit,
    onRetake: () -> Unit,
    onUpload: () -> Unit,
) {
    val bitmap = remember(file) { BitmapFactory.decodeFile(file.absolutePath)?.asImageBitmap() }
    Column(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(ReferenceSurface)
            .border(1.dp, ReferenceDivider, RoundedCornerShape(18.dp)).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Text("确认你的表情标签", color = ReferenceText, fontSize = 14.sp, fontWeight = FontWeight.Bold)
        bitmap?.let {
            Image(
                bitmap = it,
                contentDescription = "待标注的表情照片",
                modifier = Modifier.fillMaxWidth().height(230.dp).clip(RoundedCornerShape(14.dp)),
            )
        }
        Text("请选择你认为最符合当前可观察表情的标签。", color = ReferenceMuted, fontSize = 11.sp)
        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            items(ExpressionLabel.values().filterNot { it == ExpressionLabel.UNKNOWN || it == ExpressionLabel.NO_FACE }) { label ->
                FilterChip(
                    selected = selectedLabel == label,
                    onClick = { onSelectLabel(label) },
                    label = { Text(label.displayName()) },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = ReferencePrimarySoft,
                        selectedLabelColor = ReferencePrimary,
                    ),
                )
            }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(9.dp)) {
            OutlinedButton(onClick = onRetake, modifier = Modifier.weight(1f), enabled = !uploading) {
                Icon(Icons.Default.Refresh, null, Modifier.size(16.dp))
                Spacer(Modifier.size(5.dp))
                Text("重新拍摄")
            }
            Button(
                onClick = onUpload,
                enabled = selectedLabel != null && canUpload && !uploading,
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(containerColor = ReferencePrimary),
            ) {
                if (uploading) {
                    CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = Color.White)
                } else {
                    Icon(Icons.Default.CloudUpload, null, Modifier.size(16.dp))
                }
                Spacer(Modifier.size(5.dp))
                Text(if (!canUpload) "需连接真实后端" else "确认并上传")
            }
        }
    }
}

@Composable
private fun UploadedSampleCard(sampleId: String, deleting: Boolean, onDelete: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(16.dp)).background(ReferenceSurface)
            .border(1.dp, ReferenceDivider, RoundedCornerShape(16.dp)).padding(13.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Default.CheckCircle, null, tint = Success, modifier = Modifier.size(20.dp))
        Column(Modifier.weight(1f).padding(horizontal = 9.dp)) {
            Text("服务器已接收这条样本", color = ReferenceText, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
            Text("编号 ${sampleId.take(10)} · 可随时删除", color = ReferenceMuted, fontSize = 10.sp)
        }
        IconButton(onClick = onDelete, enabled = !deleting) {
            Icon(Icons.Default.DeleteOutline, "删除云端样本", tint = Danger)
        }
    }
}

@Composable
private fun StatusBanner(message: String, isError: Boolean) {
    Row(
        Modifier.fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(if (isError) AlertErrorBg else AlertInfoBg)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            Icons.Default.Info,
            null,
            tint = if (isError) AlertErrorText else AlertInfoText,
            modifier = Modifier.size(17.dp),
        )
        Spacer(Modifier.size(7.dp))
        Text(message, color = if (isError) AlertErrorText else AlertInfoText, fontSize = 11.sp)
    }
}

@Composable
private fun InfoCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    text: String,
) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(18.dp)).background(ReferenceSurface)
            .border(1.dp, ReferenceDivider, RoundedCornerShape(18.dp)).padding(16.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(icon, null, tint = ReferencePrimary, modifier = Modifier.size(20.dp))
        Column(Modifier.padding(start = 9.dp)) {
            Text(title, color = ReferenceText, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(3.dp))
            Text(text, color = ReferenceMuted, fontSize = 10.sp, lineHeight = 15.sp)
        }
    }
}

private fun ExpressionLabel.displayName(): String = when (this) {
    ExpressionLabel.HAPPY -> "开心"
    ExpressionLabel.NEUTRAL -> "中性"
    ExpressionLabel.SAD -> "低落"
    ExpressionLabel.ANGRY -> "生气"
    ExpressionLabel.FEAR -> "紧张"
    ExpressionLabel.SURPRISE -> "惊讶"
    ExpressionLabel.DISGUST -> "厌恶"
    ExpressionLabel.UNKNOWN -> "不确定"
    ExpressionLabel.NO_FACE -> "无人脸"
}
