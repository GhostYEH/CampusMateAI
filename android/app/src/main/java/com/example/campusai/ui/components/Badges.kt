package com.example.campusai.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.theme.*

@Composable
fun Avatar(
    name: String,
    modifier: Modifier = Modifier,
    size: Dp = 42.dp
) {
    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(AvatarBg),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = name.take(1),
            color = Primary,
            fontWeight = FontWeight.ExtraBold,
            fontSize = (size.value / 2.5).sp
        )
    }
}

@Composable
fun ModeBadge(mockMode: Boolean, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.padding(horizontal = 9.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        Box(
            modifier = Modifier
                .size(6.dp)
                .clip(CircleShape)
                .background(ModeBadgeDot)
        )
        Text(
            text = if (mockMode) "Mock 模式" else "真实后端",
            style = MaterialTheme.typography.labelSmall
        )
    }
}

@Composable
fun MockBadge(modifier: Modifier = Modifier) {
    Text(
        text = "Mock",
        color = MockBadgeText,
        fontSize = 9.sp,
        fontWeight = FontWeight.Normal,
        modifier = modifier
            .background(MockBadgeBg, RoundedCornerShape(4.dp))
            .padding(horizontal = 5.dp, vertical = 2.dp)
    )
}

@Composable
fun PendingBadge(count: Int, modifier: Modifier = Modifier) {
    if (count > 0) {
        Box(
            modifier = modifier
                .defaultMinSize(minWidth = 20.dp, minHeight = 20.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(PendingBadgeBg)
                .padding(horizontal = 6.dp),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = count.toString(),
                color = PendingBadgeText,
                fontSize = 11.sp,
                fontWeight = FontWeight.Bold
            )
        }
    }
}