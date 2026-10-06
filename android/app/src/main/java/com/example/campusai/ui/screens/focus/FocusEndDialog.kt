package com.example.campusai.ui.screens.focus

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog

/** Keeps the confirmation readable over the selected study atmosphere. */
@Composable
internal fun FocusEndDialog(
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
        Surface(shape = RoundedCornerShape(topStart = 7.dp, topEnd = 28.dp, bottomEnd = 7.dp, bottomStart = 7.dp),
            color = Color(0xFFF6EEDB), border = BorderStroke(1.dp, Color(0xFFD3B98B)), shadowElevation = 16.dp) {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 560.dp).verticalScroll(rememberScrollState())
                    .imePadding().padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text("STUDY NOTE  /  自习室", color = Color(0xFFA76343), fontSize = 11.sp, fontWeight = FontWeight.Bold)
                HorizontalDivider(color = Color(0xFFCAAA78), thickness = 1.dp)
                Text(
                    if (timerExpired) "这段学习完成了" else "结束本次专注？",
                    color = Color(0xFF23364B), fontSize = 23.sp, fontWeight = FontWeight.Bold,
                )
                Column(Modifier.fillMaxWidth().padding(vertical = 3.dp), verticalArrangement = Arrangement.spacedBy(5.dp)) {
                    Text("本次目标", color = Color(0xFFA76343), fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    Text(goal.ifBlank { "自由专注" }, color = Color(0xFF23364B), fontSize = 15.sp, lineHeight = 21.sp)
                }
                HorizontalDivider(color = Color(0xFFD8C6A6), thickness = 1.dp)
                Text("写下这次完成的事，也可以留空。", color = Color(0xFF667485), fontSize = 13.sp)
                OutlinedTextField(
                    value = selfReport,
                    onValueChange = { onReportChange(it.take(2_000)) },
                    label = { Text("我的学习收获（选填）") },
                    placeholder = { Text("例如：做完两道习题，下次继续第三题", color = Color(0xFF77818D)) },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(6.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = Color(0xFF23364B),
                        unfocusedTextColor = Color(0xFF23364B),
                        focusedLabelColor = Color(0xFFA76343),
                        unfocusedLabelColor = Color(0xFF667485),
                        focusedBorderColor = Color(0xFFA76343),
                        unfocusedBorderColor = Color(0xFFD3B98B),
                        cursorColor = Color(0xFFA76343),
                    ),
                )
                error?.let { Text(it, color = Color(0xFF974D42), fontSize = 12.sp) }
                Spacer(Modifier.height(2.dp))
                Button(
                    onClick = onComplete,
                    enabled = !finishing,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(7.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFFAD6845), contentColor = Color.White),
                ) {
                    Text(if (hasPlanStep) "完成步骤并查看总结" else "结束并查看总结", fontWeight = FontWeight.Bold)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    if (!timerExpired) TextButton(enabled = !finishing, onClick = onDismiss) {
                        Text("继续专注", color = Color(0xFF23364B))
                    }
                    if (hasPlanStep) TextButton(enabled = !finishing, onClick = onEndOnly) {
                        Text("仅结束专注", color = FocusStudyPalette.Muted)
                    }
                }
            }
        }
    }
}
