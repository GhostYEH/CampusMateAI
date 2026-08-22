package com.example.campusai

import com.example.campusai.data.expression.ImageProxyBitmapConverter
import org.junit.Assert.assertTrue
import org.junit.Test

class ImageProxyBitmapConverterTest {
    @Test
    fun yuv420ConversionProducesRgbPixelsWithoutJpegRoundTrip() {
        val pixels = ImageProxyBitmapConverter.yuv420ToArgb(
            width = 2,
            height = 2,
            yPlane = byteArrayOf(128.toByte(), 128.toByte(), 128.toByte(), 128.toByte()),
            yRowStride = 2,
            yPixelStride = 1,
            uPlane = byteArrayOf(128.toByte()),
            uRowStride = 1,
            uPixelStride = 1,
            vPlane = byteArrayOf(128.toByte()),
            vRowStride = 1,
            vPixelStride = 1,
        )

        assertTrue(pixels.all { pixel ->
            val red = pixel shr 16 and 0xFF
            val green = pixel shr 8 and 0xFF
            val blue = pixel and 0xFF
            red in 120..140 && green in 120..140 && blue in 120..140
        })
    }
}
