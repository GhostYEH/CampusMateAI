package com.example.campusai.ui.screens.focus

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.campusai.data.focus.scene.FocusScene

/** Keeps the confirmation inside the currently selected study atmosphere. */
@Composable
internal fun FocusEndDialog(
    scene: FocusScene,
    timerExpired: Boolean,
    finishing: Boolean,
    hasPlanStep: Boolean,
    goal: String,
    selfReport: String,
    error: String?,
    onReportChange: (String) -> Unit,
    onDismiss: () -> Unit,
    onComplete: () -> Unit,
    onEndOnly: () -> Unit,
) {
    Dialog(onDismissRequest = { if (!finishing && !timerExpired) onDismiss() }) {
        Box(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(28.dp))
                .background(Color(0xFFF8F2E8)),
        ) {
            Image(
                painter = painterResource(scene.backgroundResource()),
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.matchParentSize(),
            )
            Box(
                Modifier.matchParentSize().background(
                    Brush.verticalGradient(
                        listOf(Color(0xF8FFF9EF), Color(0xF2F8F0E5)),
                    ),
                ),
            )
            Column(
                Modifier.fillMaxWidth().padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(13.dp),
            ) {
                Text("自习室  /  本次专注", color = Color(0xFF517360), fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(
                    if (timerExpired) "这段学习完成了" else "结束本次专注？",
                    color = Color(0xFF203B32), fontSize = 23.sp, fontWeight = FontWeight.Bold,
                )
                Text("本次目标", color = Color(0xFF295643), fontSize = 13.sp, fontWeight = FontWeight.Bold)
                Text(goal.ifBlank { "自由专注" }, color = Color(0xFF203B32), fontSize = 16.sp, lineHeight = 22.sp)
                Text("写下这次完成的事，也可以留空。", color = Color(0xFF5D7066), fontSize = 13.sp)
                OutlinedTextField(
                    value = selfReport,
                    onValueChange = { onReportChange(it.take(2_000)) },
                    label = { Text("我的学习收获（选填）") },
                    placeholder = { Text("例如：做完两道习题，下次继续第三题", color = Color(0xFF63796E)) },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color(0xFF203B32),
                        unfocusedTextColor = Color(0xFF203B32),
                        focusedLabelColor = Color(0xFF295643),
                        unfocusedLabelColor = Color(0xFF5D7066),
                        focusedBorderColor = Color(0xFF295643),
                        unfocusedBorderColor = Color(0xFF93AA9A),
                        cursorColor = Color(0xFF295643),
                    ),
                )
                error?.let { Text(it, color = Color(0xFF974D42), fontSize = 12.sp) }
                Spacer(Modifier.height(2.dp))
                Button(
                    onClick = onComplete,
                    enabled = !finishing,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF295643), contentColor = Color.White),
                ) {
                    Text(if (hasPlanStep) "完成步骤并查看总结" else "结束并查看总结", fontWeight = FontWeight.Bold)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    if (!timerExpired) TextButton(enabled = !finishing, onClick = onDismiss) {
                        Text("继续专注", color = Color(0xFF295643))
                    }
                    if (hasPlanStep) TextButton(enabled = !finishing, onClick = onEndOnly) {
                        Text("仅结束专注", color = Color(0xFF63796E))
                    }
                }
            }
        }
    }
}
