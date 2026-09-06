package com.example.campusai.data.behavior

import android.graphics.RectF

/** Maps detector coordinates from an upright camera frame into a model-input bitmap. */
object CoordinateMapper {
    fun mapRect(
        sourceRect: RectF,
        sourceWidth: Int,
        sourceHeight: Int,
        targetWidth: Int,
        targetHeight: Int,
    ): RectF? {
        if (
            sourceWidth <= 0 || sourceHeight <= 0 ||
            targetWidth <= 0 || targetHeight <= 0 ||
            sourceRect.right <= sourceRect.left || sourceRect.bottom <= sourceRect.top
        ) {
            return null
        }

        val scaleX = targetWidth.toFloat() / sourceWidth
        val scaleY = targetHeight.toFloat() / sourceHeight
        val left = (sourceRect.left * scaleX).coerceIn(0f, targetWidth.toFloat())
        val top = (sourceRect.top * scaleY).coerceIn(0f, targetHeight.toFloat())
        val right = (sourceRect.right * scaleX).coerceIn(0f, targetWidth.toFloat())
        val bottom = (sourceRect.bottom * scaleY).coerceIn(0f, targetHeight.toFloat())
        return RectF(left, top, right, bottom).takeIf { it.right > it.left && it.bottom > it.top }
    }
}
