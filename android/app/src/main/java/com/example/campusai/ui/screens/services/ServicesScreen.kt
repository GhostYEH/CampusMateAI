package com.example.campusai.ui.screens.services

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Assignment
import androidx.compose.material.icons.filled.Build
import androidx.compose.material.icons.filled.CardMembership
import androidx.compose.material.icons.filled.Feedback
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.campusai.ui.components.CampusPageHeader
import com.example.campusai.ui.components.campusClickable
import com.example.campusai.ui.components.enterAnimation
import com.example.campusai.ui.screens.shell.BottomDockReservedHeight
import com.example.campusai.ui.strings.CampusStrings
import com.example.campusai.ui.theme.Background
import com.example.campusai.ui.theme.Line
import com.example.campusai.ui.theme.PrimarySoft
import com.example.campusai.ui.theme.Surface
import com.example.campusai.ui.theme.TextPrimary

private data class ServiceEntry(
    val title: String,
    val route: String,
    val icon: ImageVector,
    val iconColor: Color,
)

@Composable
fun ServicesScreen(
    reduceMotion: Boolean,
    onBack: () -> Unit,
    onNavigate: (String) -> Unit,
) {
    val entries = listOf(
        ServiceEntry(CampusStrings.Services.LEAVE, "service_leave", Icons.Default.Assignment, Color(0xFF5B68F2)),
        ServiceEntry(CampusStrings.Services.REPAIR, "service_repair", Icons.Default.Build, Color(0xFF4E8C6A)),
        ServiceEntry(CampusStrings.Services.CERTIFICATE, "service_form/certificate", Icons.Default.CardMembership, Color(0xFFE08A4E)),
        ServiceEntry(CampusStrings.Services.VENUE, "service_form/venue", Icons.Default.MeetingRoom, Color(0xFF397CEF)),
        ServiceEntry(CampusStrings.Services.FEEDBACK, "service_form/feedback", Icons.Default.Feedback, Color(0xFF7C6BE8)),
        ServiceEntry(CampusStrings.Services.MINE, "service_mine", Icons.Default.FolderOpen, Color(0xFF35B99A)),
    )

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Background)
            .padding(horizontal = 16.dp),
    ) {
        Spacer(Modifier.height(12.dp))
        CampusPageHeader(
            title = CampusStrings.Services.TITLE,
            subtitle = CampusStrings.Services.SUBTITLE,
            onBack = onBack,
        )
        Spacer(Modifier.height(14.dp))
        LazyVerticalGrid(
            columns = GridCells.Fixed(2),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(
                bottom = WindowInsets.navigationBars.asPaddingValues()
                    .calculateBottomPadding() + BottomDockReservedHeight + 16.dp,
            ),
        ) {
            items(entries, key = { it.route }) { entry ->
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clip(RoundedCornerShape(18.dp))
                        .background(Surface)
                        .campusClickable { onNavigate(entry.route) }
                        .enterAnimation(enabled = !reduceMotion)
                        .padding(16.dp),
                ) {
                    Box(
                        modifier = Modifier
                            .size(42.dp)
                            .clip(RoundedCornerShape(12.dp))
                            .background(entry.iconColor.copy(alpha = .12f)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(entry.icon, entry.title, tint = entry.iconColor, modifier = Modifier.size(22.dp))
                    }
                    Spacer(Modifier.height(12.dp))
                    Text(entry.title, color = TextPrimary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}
