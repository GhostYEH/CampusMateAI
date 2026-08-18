package com.example.campusai.ui.screens.profile

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.QrPayloadParser
import com.example.campusai.data.remote.QrScanRequest
import com.example.campusai.ui.theme.*
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

import java.util.concurrent.Executors@Composable
fun QrScannerScreen(
    onBack: () -> Unit,
    onScanned: (sessionId: String, scanToken: String, browserName: String?, osName: String?, deviceLabel: String?) -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val scope = rememberCoroutineScope()

    var hasCameraPermission by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED,
        )
    }
    var scanError by remember { mutableStateOf<String?>(null) }
    var isProcessing by remember { mutableStateOf(false) }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        hasCameraPermission = granted
        if (!granted) scanError = "需要相机权限才能扫码"
    }

    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }

    Box(Modifier.fillMaxSize().background(Color.Black)) {
        if (hasCameraPermission) {
            CameraPreviewWithBarcode(
                onBarcodeDetected = { rawValue ->
                    if (isProcessing) return@CameraPreviewWithBarcode
                    val parsed = QrPayloadParser.parse(rawValue)
                    if (parsed == null) {
                        scanError = "不是有效的 CampusMate 登录二维码"
                        return@CameraPreviewWithBarcode
                    }
                    isProcessing = true
                    scanError = null
                    scope.launch(Dispatchers.IO) {
                        try {
                            val resp = ApiClient.api.qrScan(
                                QrScanRequest(parsed.sessionId, parsed.scanToken),
                            )
                            if (resp.isSuccessful) {
                                val body = resp.body()!!
                                onScanned(
                                    body.session_id,
                                    parsed.scanToken,
                                    body.browser_name,
                                    body.os_name,
                                    body.device_label,
                                )
                            } else {
                                val errBody = resp.errorBody()?.string() ?: ""
                                scanError = when {
                                    errBody.contains("QR_EXPIRED") -> "二维码已过期"
                                    errBody.contains("QR_ALREADY_SCANNED") -> "二维码已被扫描"
                                    errBody.contains("QR_CANCELLED") -> "二维码已取消"
                                    errBody.contains("QR_INVALID") -> "二维码无效"
                                    else -> "扫码失败，请重试"
                                }
                                isProcessing = false
                            }
                        } catch (e: Exception) {
                            scanError = "网络错误，请检查连接"
                            isProcessing = false
                        }
                    }
                },
            )
            ScanOverlay()
        }

        // 顶部导航栏
        Row(
            Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.Default.ArrowBack, contentDescription = "返回", tint = Color.White)
            }
            Text("扫一扫", color = Color.White, fontSize = 18.sp, fontWeight = FontWeight.Bold)
        }

        // 底部提示
        Column(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().padding(bottom = 48.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            if (scanError != null) {
                Text(scanError!!, color = Color(0xFFF2674F), fontSize = 14.sp, fontWeight = FontWeight.Medium)
                Spacer(Modifier.height(8.dp))
            }
            Text("将二维码放入框内，即可自动扫描", color = Color.White.copy(alpha = 0.7f), fontSize = 13.sp)
        }
    }
}

@Composable
private fun CameraPreviewWithBarcode(onBarcodeDetected: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember { PreviewView(context) }
    val executor = remember { Executors.newSingleThreadExecutor() }
    val processed = remember { mutableStateOf(false) }

    DisposableEffect(Unit) {
        onDispose { executor.shutdown() }
    }

    AndroidView(
        factory = { previewView },
        modifier = Modifier.fillMaxSize(),
    )

    LaunchedEffect(Unit) {
        val cameraProviderFuture = ProcessCameraProvider.getInstance(context)
        cameraProviderFuture.addListener({
            val cameraProvider = cameraProviderFuture.get()
            val preview = Preview.Builder().build().also {
                it.setSurfaceProvider(previewView.surfaceProvider)
            }
            val analyzer = ImageAnalysis.Builder()
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
                .build()
            analyzer.setAnalyzer(executor) { imageProxy ->
                processBarcode(imageProxy) { rawValue ->
                    if (!processed.value && rawValue != null) {
                        processed.value = true
                        onBarcodeDetected(rawValue)
                    }
                }
            }
            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    preview,
                    analyzer,
                )
            } catch (e: Exception) { /* ignore */ }
        }, ContextCompat.getMainExecutor(context))
    }
}

private fun processBarcode(imageProxy: ImageProxy, onResult: (String?) -> Unit) {
    val mediaImage = imageProxy.image
    if (mediaImage == null) {
        imageProxy.close()
        onResult(null)
        return
    }
    val inputImage = InputImage.fromMediaImage(mediaImage, imageProxy.imageInfo.rotationDegrees)
    val options = BarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .build()
    val scanner = BarcodeScanning.getClient(options)
    scanner.process(inputImage)
        .addOnSuccessListener { barcodes ->
            val raw = barcodes.firstOrNull()?.rawValue
            onResult(raw)
        }
        .addOnFailureListener { onResult(null) }
        .addOnCompleteListener { imageProxy.close() }
}

@Composable
private fun ScanOverlay() {
    Box(Modifier.fillMaxSize()) {
        // 半透明遮罩 + 中央透明框
        val frameSize = 260.dp
        Box(Modifier.align(Alignment.Center)) {
            // 四角扫描线
            val cornerLen = 24.dp
            val cornerWidth = 3.dp
            Box(
                Modifier.size(frameSize).align(Alignment.Center),
            ) {
                // 左上角
                Box(Modifier.size(cornerLen, cornerWidth).background(Primary).align(Alignment.TopStart))
                Box(Modifier.size(cornerWidth, cornerLen).background(Primary).align(Alignment.TopStart))
                // 右上角
                Box(Modifier.size(cornerLen, cornerWidth).background(Primary).align(Alignment.TopEnd))
                Box(Modifier.size(cornerWidth, cornerLen).background(Primary).align(Alignment.TopEnd))
                // 左下角
                Box(Modifier.size(cornerLen, cornerWidth).background(Primary).align(Alignment.BottomStart))
                Box(Modifier.size(cornerWidth, cornerLen).background(Primary).align(Alignment.BottomStart))
                // 右下角
                Box(Modifier.size(cornerLen, cornerWidth).background(Primary).align(Alignment.BottomEnd))
                Box(Modifier.size(cornerWidth, cornerLen).background(Primary).align(Alignment.BottomEnd))
            }
        }
    }
}