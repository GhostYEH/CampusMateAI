package com.example.campusai.data.behavior

import kotlin.math.ceil
import kotlin.math.floor

data class BehaviorRoi(
    val left: Int,
    val top: Int,
    val right: Int,
    val bottom: Int,
) {
    val width: Int get() = right - left
    val height: Int get() = bottom - top

    companion object {
        fun from(
            left: Float,
            top: Float,
            right: Float,
            bottom: Float,
            imageWidth: Int,
            imageHeight: Int,
            paddingFraction: Float = 0.10f,
        ): BehaviorRoi? {
            if (imageWidth <= 0 || imageHeight <= 0 || right <= left || bottom <= top) return null
            val padding = paddingFraction.coerceAtLeast(0f)
            val horizontalPadding = (right - left) * padding
            val verticalPadding = (bottom - top) * padding
            val boundedLeft = floor(left - horizontalPadding).toInt().coerceIn(0, imageWidth)
            val boundedTop = floor(top - verticalPadding).toInt().coerceIn(0, imageHeight)
            val boundedRight = ceil(right + horizontalPadding).toInt().coerceIn(0, imageWidth)
            val boundedBottom = ceil(bottom + verticalPadding).toInt().coerceIn(0, imageHeight)
            if (boundedRight <= boundedLeft || boundedBottom <= boundedTop) return null
            return BehaviorRoi(boundedLeft, boundedTop, boundedRight, boundedBottom)
        }
    }
}

