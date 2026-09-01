package com.example.campusai.ui.screens.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.School
import com.example.campusai.ui.components.GlassButton as Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.theme.AlertErrorText
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Primary
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary
import kotlinx.coroutines.launch

/** Reusable form embedded directly in the 学习通同步 screen. */
@Composable
fun ChaoxingLoginForm(
    viewModel: ChaoxingViewModel,
    headline: String = "学习通账号登录",
    helperText: String = "仅用于连接学习通，本地不会保存你的密码。",
) {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.School, null, tint = Primary, modifier = Modifier.size(28.dp))
            Spacer(Modifier.width(8.dp))
            Text(headline, fontSize = 15.sp, fontWeight = FontWeight.SemiBold, color = TextPrimary)
        }
        Text(helperText, color = Muted, fontSize = 12.sp)
        OutlinedTextField(
            value = username,
            onValueChange = { username = it },
            label = { Text("学号 / 手机号") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            shape = RoundedCornerShape(10.dp),
        )
        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("密码") },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            shape = RoundedCornerShape(10.dp),
            visualTransformation = PasswordVisualTransformation(),
        )
        Button(
            onClick = {
                isLoading = true
                error = null
                scope.launch {
                    val (success, message) = viewModel.login(username, password)
                    isLoading = false
                    if (success) password = "" else error = when (message) {
                        "verification_required" -> "当前登录需要验证码，请先在学习通官方 App 或网页完成验证后重试。"
                        else -> message
                    }
                }
            },
            enabled = username.isNotBlank() && password.isNotBlank() && !isLoading,
            modifier = Modifier.fillMaxWidth().height(46.dp),
            shape = RoundedCornerShape(10.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Primary),
        ) {
            if (isLoading) {
                CircularProgressIndicator(Modifier.size(16.dp), color = Surface, strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("登录中…", fontWeight = FontWeight.SemiBold)
            } else Text("登录并连接", fontWeight = FontWeight.SemiBold)
        }
        error?.let { message ->
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.Info, null, tint = AlertErrorText, modifier = Modifier.size(14.dp))
                Text(message, color = AlertErrorText, fontSize = 12.sp)
            }
        }
    }
}
