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
        Surface(shape = RoundedCornerShape(28.dp), color = FocusStudyPalette.Paper,
            border = BorderStroke(1.dp, FocusStudyPalette.Line), shadowElevation = 16.dp) {
            Column(
                Modifier.fillMaxWidth().heightIn(max = 560.dp).verticalScroll(rememberScrollState())
                    .imePadding().padding(22.dp),
                verticalArrangement = Arrangement.spacedBy(13.dp),
            ) {
                Box(Modifier.fillMaxWidth().height(3.dp).clip(RoundedCornerShape(3.dp))
                    .background(FocusStudyPalette.Copper))
                Text("自习室  /  本次专注", color = FocusStudyPalette.Pine, fontSize = 11.sp, fontWeight = FontWeight.Bold)
                Text(
                    if (timerExpired) "这段学习完成了" else "结束本次专注？",
                    color = FocusStudyPalette.Ink, fontSize = 23.sp, fontWeight = FontWeight.Bold,
                )
                Surface(shape = RoundedCornerShape(16.dp), color = FocusStudyPalette.PaperSoft) {
                    Column(Modifier.fillMaxWidth().padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("本次目标", color = FocusStudyPalette.Pine, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                        Text(goal.ifBlank { "自由专注" }, color = FocusStudyPalette.Ink, fontSize = 15.sp, lineHeight = 21.sp)
                    }
                }
                Text("写下这次完成的事，也可以留空。", color = FocusStudyPalette.Muted, fontSize = 13.sp)
                OutlinedTextField(
                    value = selfReport,
                    onValueChange = { onReportChange(it.take(2_000)) },
                    label = { Text("我的学习收获（选填）") },
                    placeholder = { Text("例如：做完两道习题，下次继续第三题", color = FocusStudyPalette.Muted) },
                    minLines = 2,
                    maxLines = 4,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedTextColor = FocusStudyPalette.Ink,
                        unfocusedTextColor = FocusStudyPalette.Ink,
                        focusedLabelColor = FocusStudyPalette.Pine,
                        unfocusedLabelColor = FocusStudyPalette.Muted,
                        focusedBorderColor = FocusStudyPalette.Pine,
                        unfocusedBorderColor = FocusStudyPalette.Line,
                        cursorColor = FocusStudyPalette.Pine,
                    ),
                )
                error?.let { Text(it, color = Color(0xFF974D42), fontSize = 12.sp) }
                Spacer(Modifier.height(2.dp))
                Button(
                    onClick = onComplete,
                    enabled = !finishing,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = FocusStudyPalette.Pine, contentColor = Color.White),
                ) {
                    Text(if (hasPlanStep) "完成步骤并查看总结" else "结束并查看总结", fontWeight = FontWeight.Bold)
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    if (!timerExpired) TextButton(enabled = !finishing, onClick = onDismiss) {
                        Text("继续专注", color = FocusStudyPalette.Pine)
                    }
                    if (hasPlanStep) TextButton(enabled = !finishing, onClick = onEndOnly) {
                        Text("仅结束专注", color = FocusStudyPalette.Muted)
                    }
                }
            }
        }
    }
}
