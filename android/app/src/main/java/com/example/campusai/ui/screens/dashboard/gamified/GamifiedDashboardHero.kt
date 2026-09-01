package com.example.campusai.ui.screens.dashboard.gamified

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.snap
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.LocalFireDepartment
import androidx.compose.material.icons.filled.Stars
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.screens.profile.ReferenceAvatar
import com.example.campusai.ui.theme.GamificationTokens
import com.example.campusai.ui.theme.Muted
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

@Composable
internal fun PlayerHeader(
    player: PlayerUiState,
    reduceMotion: Boolean,
    onOpenProfile: () -> Unit,
) {
    val progress by animateFloatAsState(
        targetValue = player.progress.coerceIn(0f, 1f),
        animationSpec = if (reduceMotion) snap() else tween(650),
        label = "player-level-progress",
    )
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Surface)
            .campusClickable(onClick = onOpenProfile)
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box {
            ReferenceAvatar(size = 52.dp)
            Box(
                modifier = Modifier
                    .align(Alignment.BottomEnd)
                    .clip(CircleShape)
                    .background(GamificationTokens.CampusBlue)
                    .padding(horizontal = 6.dp, vertical = 3.dp),
            ) {
                Text("${player.level}", color = Color.White, fontSize = 9.sp, fontWeight = FontWeight.Bold)
            }
        }
        Column(Modifier.padding(start = 13.dp).weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(player.name, color = TextPrimary, fontSize = 17.sp, fontWeight = FontWeight.Bold, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                Text("  Lv.${player.level}", color = GamificationTokens.CampusBlue, fontSize = 11.sp, fontWeight = FontWeight.Bold)
            }
            Text(player.title, color = Muted, fontSize = 11.sp)
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(6.dp).clip(CircleShape),
                color = GamificationTokens.CampusBlue,
                trackColor = GamificationTokens.CampusBlue.copy(alpha = .12f),
            )
            Spacer(Modifier.height(5.dp))
            Row {
                Text("${player.currentXp} / ${player.nextLevelXp} XP", color = Muted, fontSize = 9.5.sp)
                Spacer(Modifier.weight(1f))
                Icon(Icons.Default.LocalFireDepartment, null, tint = GamificationTokens.XpAmber, modifier = Modifier.size(14.dp))
                Text(" 连续 ${player.streakDays} 天", color = Muted, fontSize = 9.5.sp)
            }
        }
    }
}

@Composable
internal fun DailyAdventureHero(
    adventure: DailyAdventureUiState,
    reduceMotion: Boolean,
    onNavigate: (String) -> Unit,
) {
    val progress by animateFloatAsState(
        targetValue = adventure.progress.coerceIn(0f, 1f),
        animationSpec = if (reduceMotion) snap() else tween(750),
        label = "daily-adventure-progress",
    )
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .height(214.dp)
            .clip(RoundedCornerShape(30.dp))
            .background(
                Brush.linearGradient(
                    listOf(GamificationTokens.CampusBlueDeep, GamificationTokens.Indigo, GamificationTokens.Purple),
                ),
            )
            .campusClickable { onNavigate(adventure.route) },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            drawCircle(GamificationTokens.Glow.copy(alpha = .16f), radius = size.minDimension * .55f, center = Offset(size.width * .88f, size.height * .05f))
            drawCircle(Color.White.copy(alpha = .08f), radius = size.minDimension * .26f, center = Offset(size.width * .74f, size.height * .72f))
        }
        Column(Modifier.fillMaxSize().padding(22.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.clip(CircleShape).background(Color.White.copy(alpha = .13f)).padding(horizontal = 10.dp, vertical = 6.dp)) {
                    Text("DAILY ADVENTURE", color = GamificationTokens.HeroMuted, fontSize = 9.sp, fontWeight = FontWeight.Bold, letterSpacing = 1.sp)
                }
                Spacer(Modifier.weight(1f))
                Icon(Icons.Default.Stars, null, tint = GamificationTokens.XpAmber, modifier = Modifier.size(25.dp))
            }
            Spacer(Modifier.height(15.dp))
            Text(adventure.title, color = GamificationTokens.HeroText, fontSize = 25.sp, fontWeight = FontWeight.Bold)
            Text(adventure.subtitle, color = GamificationTokens.HeroMuted, fontSize = 12.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
            Spacer(Modifier.weight(1f))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${adventure.completed} / ${adventure.total} 完成", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
                Spacer(Modifier.weight(1f))
                if (adventure.nextRewardXp > 0) Text("+${adventure.nextRewardXp} XP", color = GamificationTokens.XpAmber, fontSize = 12.sp, fontWeight = FontWeight.Bold)
            }
            Spacer(Modifier.height(8.dp))
            LinearProgressIndicator(
                progress = { progress },
                modifier = Modifier.fillMaxWidth().height(8.dp).clip(CircleShape),
                color = GamificationTokens.XpAmber,
                trackColor = Color.White.copy(alpha = .16f),
            )
            Spacer(Modifier.height(13.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("继续冒险", color = Color.White, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = Color.White, modifier = Modifier.padding(start = 5.dp).size(17.dp))
            }
        }
    }
}
