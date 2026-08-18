package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ArrowBack
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.QrConfirmRequest
import com.example.campusai.data.remote.QrScanRequest
import com.example.campusai.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Composable
fun QrConfirmScreen(
    sessionId: String,
    scanToken: String,
    browserName: String?,
    osName: String?,
    deviceLabel: String?,
    onBack: () -> Unit,
    onSuccess: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var trustDevice by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var success by remember { mutableStateOf(false) }

    val deviceText = deviceLabel ?: listOfNotNull(browserName, osName).joinToString(" · ").ifEmpty { "Web 浏览器" }

    Box(Modifier.fillMaxSize().background(Background)) {
        Column(Modifier.fillMaxSize()) {
            // 顶部导航栏
            Row(
                Modifier.fillMaxWidth().statusBarsPadding().padding(horizontal = 12.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack, enabled = !loading) {
                    Icon(Icons.Default.ArrowBack, contentDescription = "返回", tint = TextPrimary)
                }
                Text("确认登录", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
            }

            if (success) {
                // 成功状态
                Column(
                    Modifier.fillMaxSize(),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Box(
                        Modifier.size(72.dp).clip(CircleShape).background(Success.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Computer, contentDescription = null, tint = Success, modifier = Modifier.size(36.dp))
                    }
                    Spacer(Modifier.height(16.dp))
                    Text("已确认登录", color = TextPrimary, fontSize = 20.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(8.dp))
                    Text("请在 Web 端查看", color = Muted, fontSize = 14.sp)
                }
            } else {
                Column(
                    Modifier.fillMaxSize().padding(horizontal = 28.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Spacer(Modifier.weight(1f))

                    // 中央电脑图标
                    Box(
                        Modifier.size(88.dp).clip(CircleShape)
                            .background(Brush.horizontalGradient(listOf(PrimaryHover, Primary))),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Default.Computer, contentDescription = null, tint = Color.White, modifier = Modifier.size(44.dp))
                    }
                    Spacer(Modifier.height(24.dp))

                    Text("登录 CampusMate Web", color = TextPrimary, fontSize = 22.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.height(12.dp))
                    Text(deviceText, color = Primary, fontSize = 16.sp, fontWeight = FontWeight.Medium)
                    Spacer(Modifier.height(8.dp))
                    Text("请确认是你本人在此设备上操作", color = Muted, fontSize = 14.sp)

                    Spacer(Modifier.weight(1f))

                    // 信任设备复选框
                    Row(
                        Modifier.fillMaxWidth().clickable { trustDevice = !trustDevice }.padding(vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = trustDevice,
                            onCheckedChange = { trustDevice = it },
                            colors = CheckboxDefaults.colors(checkedColor = Primary),
                        )
                        Text("信任当前设备自动登录", color = TextPrimary, fontSize = 14.sp)
                    }

                    if (error != null) {
                        Text(error!!, color = Danger, fontSize = 13.sp, modifier = Modifier.padding(vertical = 4.dp))
                    }

                    Spacer(Modifier.height(12.dp))

                    // 主按钮
                    Button(
                        onClick = {
                            if (loading) return@Button
                            loading = true
                            error = null
                            scope.launch(Dispatchers.IO) {
                                try {
                                    val resp = ApiClient.api.qrConfirm(
                                        QrConfirmRequest(sessionId, scanToken, trustDevice),
                                    )
                                    if (resp.isSuccessful) {
                                        success = true
                                        loading = false
                                    } else {
                                        val errBody = resp.errorBody()?.string() ?: ""
                                        error = when {
                                            errBody.contains("QR_USER_MISMATCH") -> "确认用户与扫描用户不一致"
                                            errBody.contains("QR_EXPIRED") -> "二维码已过期"
                                            errBody.contains("QR_ALREADY_CONFIRMED") -> "二维码已确认"
                                            errBody.contains("QR_CANCELLED") -> "二维码已取消"
                                            else -> "确认失败，请重试"
                                        }
                                        loading = false
                                    }
                                } catch (e: Exception) {
                                    error = "网络错误，请检查连接"
                                    loading = false
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth().height(50.dp),
                        shape = RoundedCornerShape(13.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = Primary),
                        enabled = !loading,
                    ) {
                        Text(if (loading) "正在确认…" else "登录 Web 端", fontSize = 16.sp, fontWeight = FontWeight.Bold)
                    }

                    Spacer(Modifier.height(12.dp))

                    // 取消按钮
                    TextButton(
                        onClick = {
                            if (loading) return@TextButton
                            scope.launch(Dispatchers.IO) {
                                try { ApiClient.api.qrCancel(QrScanRequest(sessionId, scanToken)) } catch (_: Exception) {}
                            }
                            onBack()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !loading,
                    ) {
                        Text("取消", color = Muted, fontSize = 15.sp)
                    }

                    Spacer(Modifier.height(32.dp))
                }
            }
        }
    }

    // 成功后自动返回
    LaunchedEffect(success) {
        if (success) {
            kotlinx.coroutines.delay(1500)
            onSuccess()
        }
    }
}