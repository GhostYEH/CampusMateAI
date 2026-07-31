package com.example.campusai.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.ReadOnlyComposable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

@Immutable
data class CampusColors(
    val primary: Color,
    val primaryHover: Color,
    val primarySoft: Color,
    val accent: Color,
    val danger: Color,
    val success: Color,
    val textPrimary: Color,
    val muted: Color,
    val line: Color,
    val surface: Color,
    val background: Color,
    val dangerText: Color,
    val successText: Color,
    val loginBg: Color,
    val loginShadeStart: Color,
    val loginShadeMid: Color,
    val loginShadeEnd: Color,
    val loginPanelBg: Color,
    val sidebarActiveBg: Color,
    val sidebarActiveText: Color,
    val avatarBg: Color,
    val chatAssistantBg: Color,
    val chatUserBg: Color,
    val robotAvatarBg: Color,
    val modeBadgeDot: Color,
    val mockBadgeBg: Color,
    val mockBadgeText: Color,
    val unreadDot: Color,
    val pendingBadgeBg: Color,
    val pendingBadgeText: Color,
    val focusRing: Color,
    val inputBorder: Color,
    val inputFocusBorder: Color,
    val inputFocusShadow: Color,
    val alertErrorBg: Color,
    val alertErrorText: Color,
    val alertInfoBg: Color,
    val alertInfoText: Color,
)

internal val LightCampusColors = CampusColors(
    primary = Color(0xFF5B68F2),
    primaryHover = Color(0xFF4E5EDB),
    primarySoft = Color(0xFFEFF0FF),
    accent = Color(0xFFE08A4E),
    danger = Color(0xFFC25450),
    success = Color(0xFF4E8C6A),
    textPrimary = Color(0xFF1B2730),
    muted = Color(0xFF667784),
    line = Color(0xFFE2E7EC),
    surface = Color(0xFFFFFFFF),
    background = Color(0xFFF6F8FA),
    dangerText = Color(0xFFE35F42),
    successText = Color(0xFF4E8C6A),
    loginBg = Color(0xFF071424),
    loginShadeStart = Color(0x7A020C19),
    loginShadeMid = Color(0xBA020C19),
    loginShadeEnd = Color(0xE0020C19),
    loginPanelBg = Color(0xFFF8FBFD),
    sidebarActiveBg = Color(0xFFEFF0FF),
    sidebarActiveText = Color(0xFF4E5EDB),
    avatarBg = Color(0xFFE2E5FF),
    chatAssistantBg = Color(0xFFF0F1FF),
    chatUserBg = Color(0xFFF2F3FF),
    robotAvatarBg = Color(0xFFE1E5FF),
    modeBadgeDot = Color(0xFFE08A4E),
    mockBadgeBg = Color(0xFFEFF0FF),
    mockBadgeText = Color(0xFF4E5EDB),
    unreadDot = Color(0xFFED6E52),
    pendingBadgeBg = Color(0xFFED6E52),
    pendingBadgeText = Color.White,
    focusRing = Color(0xFF7AB6DC),
    inputBorder = Color(0xFFCAD5DD),
    inputFocusBorder = Color(0xFF5B68F2),
    inputFocusShadow = Color(0xFFE1E4FF),
    alertErrorBg = Color(0xFFF6DAD8),
    alertErrorText = Color(0xFF8E3430),
    alertInfoBg = Color(0xFFEFF0FF),
    alertInfoText = Color(0xFF4E5EDB),
)

internal val DarkCampusColors = LightCampusColors.copy(
    primary = Color(0xFF9AA4FF),
    primaryHover = Color(0xFFB5BDFF),
    primarySoft = Color(0xFF282D5A),
    accent = Color(0xFFF0A56E),
    danger = Color(0xFFE68780),
    success = Color(0xFF79B492),
    textPrimary = Color(0xFFE8F0F4),
    muted = Color(0xFFA6B5BE),
    line = Color(0xFF2B3C46),
    surface = Color(0xFF14232C),
    background = Color(0xFF0C171E),
    dangerText = Color(0xFFF09A8F),
    successText = Color(0xFF83C09D),
    loginPanelBg = Color(0xFF14232C),
    sidebarActiveBg = Color(0xFF282D5A),
    sidebarActiveText = Color(0xFFB5BDFF),
    avatarBg = Color(0xFF30366B),
    chatAssistantBg = Color(0xFF252A50),
    chatUserBg = Color(0xFF2C3264),
    robotAvatarBg = Color(0xFF30366B),
    mockBadgeBg = Color(0xFF30366B),
    mockBadgeText = Color(0xFFB5BDFF),
    inputBorder = Color(0xFF40535E),
    inputFocusBorder = Color(0xFF9AA4FF),
    inputFocusShadow = Color(0xFF252A50),
    alertErrorBg = Color(0xFF482A2A),
    alertErrorText = Color(0xFFF2A29B),
    alertInfoBg = Color(0xFF282D5A),
    alertInfoText = Color(0xFFB5BDFF),
)

internal val LocalCampusColors = staticCompositionLocalOf { LightCampusColors }

val Primary: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.primary
val PrimaryHover: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.primaryHover
val PrimarySoft: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.primarySoft
val Accent: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.accent
val Danger: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.danger
val Success: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.success
val TextPrimary: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.textPrimary
val Muted: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.muted
val Line: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.line
val Surface: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.surface
val Background: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.background
val DangerText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.dangerText
val SuccessText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.successText
val LoginBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.loginBg
val LoginShadeStart: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.loginShadeStart
val LoginShadeMid: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.loginShadeMid
val LoginShadeEnd: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.loginShadeEnd
val LoginPanelBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.loginPanelBg
val SidebarActiveBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.sidebarActiveBg
val SidebarActiveText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.sidebarActiveText
val AvatarBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.avatarBg
val ChatAssistantBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.chatAssistantBg
val ChatUserBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.chatUserBg
val RobotAvatarBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.robotAvatarBg
val ModeBadgeDot: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.modeBadgeDot
val MockBadgeBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.mockBadgeBg
val MockBadgeText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.mockBadgeText
val UnreadDot: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.unreadDot
val PendingBadgeBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.pendingBadgeBg
val PendingBadgeText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.pendingBadgeText
val FocusRing: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.focusRing
val InputBorder: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.inputBorder
val InputFocusBorder: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.inputFocusBorder
val InputFocusShadow: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.inputFocusShadow
val AlertErrorBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.alertErrorBg
val AlertErrorText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.alertErrorText
val AlertInfoBg: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.alertInfoBg
val AlertInfoText: Color @Composable @ReadOnlyComposable get() = LocalCampusColors.current.alertInfoText
