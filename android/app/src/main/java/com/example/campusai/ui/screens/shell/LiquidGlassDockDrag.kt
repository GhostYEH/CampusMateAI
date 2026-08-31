package com.example.campusai.ui.screens.shell

import kotlin.math.roundToInt

internal fun clampDockDragOffset(
    selectedIndex: Int,
    itemCount: Int,
    itemWidthPx: Float,
    requestedOffsetPx: Float,
): Float {
    if (itemCount <= 0 || itemWidthPx <= 0f) return 0f
    val safeSelectedIndex = selectedIndex.coerceIn(0, itemCount - 1)
    val minimumOffset = -safeSelectedIndex * itemWidthPx
    val maximumOffset = (itemCount - 1 - safeSelectedIndex) * itemWidthPx
    return requestedOffsetPx.coerceIn(minimumOffset, maximumOffset)
}

internal fun dockDragTargetIndex(
    selectedIndex: Int,
    dragOffsetPx: Float,
    itemWidthPx: Float,
    itemCount: Int,
): Int {
    if (itemCount <= 0) return 0
    val safeSelectedIndex = selectedIndex.coerceIn(0, itemCount - 1)
    if (itemWidthPx <= 0f) return safeSelectedIndex
    return (safeSelectedIndex + dragOffsetPx / itemWidthPx)
        .roundToInt()
        .coerceIn(0, itemCount - 1)
}
