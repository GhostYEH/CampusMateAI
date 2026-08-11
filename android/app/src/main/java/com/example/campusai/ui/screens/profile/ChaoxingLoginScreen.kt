package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.School
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.theme.AlertErrorText
import androidx.compose.ui.graphics.Color
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

@Composable
fun ChaoxingLoginScreen(viewModel: ChaoxingViewModel = viewModel(), onLoginSuccess: () -> Unit) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .imePadding()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp)
            .padding(top = 16.dp, bottom = BottomDockReservedHeight + 24.dp),
    ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(PrimarySoft),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Default.School, null, tint = Primary, modifier = Modifier.size(18.dp))
                }
                Spacer(Modifier.width(10.dp))
                Text("学习通账号登录", fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                "仅用于连接学习通，本地不会保存你的密码。",
                color = Muted,
                fontSize = 12.sp,
            )

            Spacer(Modifier.height(18.dp))
            OutlinedTextField(
                value = username,
                onValueChange = { username = it },
                label = { Text("学号 / 手机号") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                shape = RoundedCornerShape(10.dp),
            )
            Spacer(Modifier.height(10.dp))
            OutlinedTextField(
                value = password,
                onValueChange = { password = it },
                label = { Text("密码") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
                shape = RoundedCornerShape(10.dp),
                visualTransformation = PasswordVisualTransformation(),
            )

            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    isLoading = true
                    error = null
                    scope.launch {
                        val (success, msg) = viewModel.login(username, password)
                        isLoading = false
                        if (success) {
                            onLoginSuccess()
                        } else {
                            error = if (msg == "verification_required") {
                                "当前登录需要验证码，请先在学习通官方 App 或网页完成验证后重试。"
                            } else {
                                msg
                            }
                        }
                    }
                },
                enabled = username.isNotBlank() && password.isNotBlank() && !isLoading,
                modifier = Modifier.fillMaxWidth().height(46.dp),
                shape = RoundedCornerShape(10.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Primary),
            ) {
                if (isLoading) {
                    CircularProgressIndicator(modifier = Modifier.size(16.dp), color = Surface, strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("登录中…", fontWeight = FontWeight.SemiBold)
                } else {
                    Text("登录", fontWeight = FontWeight.SemiBold)
                }
            }

            error?.let { msg ->
                Spacer(Modifier.height(12.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Default.Info, null, tint = AlertErrorText, modifier = Modifier.size(14.dp))
                    Text(msg, color = AlertErrorText, fontSize = 12.sp)
                }
            }
    }
}
