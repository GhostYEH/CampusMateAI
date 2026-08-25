package com.example.campusai.ui.screens.counselor

internal const val CPM_RECOMMENDATION_CARD_HEIGHT_DP = 64
internal const val CPM_COMPOSER_MIN_HEIGHT_DP = 60

internal data class CpmHeroMetrics(
    val cardHeightDp: Int,
    val avatarSizeDp: Int,
    val contentPaddingDp: Int,
    val itemGapDp: Int,
    val controlHeightDp: Int,
    val avatarScale: Float,
    val avatarContainerScale: Float,
    val avatarVerticalOffsetFraction: Float,
    val sparkleBadgeSizeDp: Int,
    val alignAvatarToTop: Boolean,
)

internal fun cpmHeroMetrics(maxWidthDp: Int): CpmHeroMetrics = if (maxWidthDp <= 380) {
    CpmHeroMetrics(
        cardHeightDp = 240,
        avatarSizeDp = 146,
        contentPaddingDp = 16,
        itemGapDp = 14,
        controlHeightDp = 70,
        avatarScale = 1.68f,
        avatarContainerScale = 1.00f,
        avatarVerticalOffsetFraction = 0.34f,
        sparkleBadgeSizeDp = 34,
        alignAvatarToTop = true,
    )
} else {
    CpmHeroMetrics(
        cardHeightDp = 240,
        avatarSizeDp = 148,
        contentPaddingDp = 18,
        itemGapDp = 18,
        controlHeightDp = 72,
        avatarScale = 1.68f,
        avatarContainerScale = 1.00f,
        avatarVerticalOffsetFraction = 0.34f,
        sparkleBadgeSizeDp = 34,
        alignAvatarToTop = true,
    )
}
