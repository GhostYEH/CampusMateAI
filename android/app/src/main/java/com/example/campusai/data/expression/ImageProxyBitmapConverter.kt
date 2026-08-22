package com.example.campusai.data.expression

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import android.os.SystemClock
import androidx.camera.core.ImageProxy
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer

object ImageProxyBitmapConverter {
    private val argbBuffer = ThreadLocal<IntArray>()

    data class ConversionBenchmark(
        val directRgbMs: Long,
        val legacyJpegMs: Long,
    )

    fun toUprightMirroredBitmap(image: ImageProxy, mirror: Boolean): Bitmap {
        val argb = yuv420888ToArgb(image)
        val bitmap = Bitmap.createBitmap(argb, image.width, image.height, Bitmap.Config.ARGB_8888)
        return transform(bitmap, image.imageInfo.rotationDegrees.toFloat(), mirror)
    }

    /**
     * Debug/instrumentation helper for comparing the production path with the old JPEG path.
     * It only returns timings and recycles both temporary bitmaps.
     */
    fun benchmark(image: ImageProxy, mirror: Boolean): ConversionBenchmark {
        val directStartedAt = SystemClock.elapsedRealtimeNanos()
        toUprightMirroredBitmap(image, mirror).recycle()
        val directMs = elapsedMs(directStartedAt)

        val legacyStartedAt = SystemClock.elapsedRealtimeNanos()
        toUprightMirroredBitmapLegacy(image, mirror).recycle()
        val legacyMs = elapsedMs(legacyStartedAt)
        return ConversionBenchmark(directRgbMs = directMs, legacyJpegMs = legacyMs)
    }

    private fun toUprightMirroredBitmapLegacy(image: ImageProxy, mirror: Boolean): Bitmap {
        val nv21 = yuv420888ToNv21(image)
        val jpeg = ByteArrayOutputStream().use { output ->
            YuvImage(nv21, ImageFormat.NV21, image.width, image.height, null)
                .compressToJpeg(Rect(0, 0, image.width, image.height), 90, output)
            output.toByteArray()
        }
        val bitmap = checkNotNull(BitmapFactory.decodeByteArray(jpeg, 0, jpeg.size)) {
            "Unable to decode camera frame"
        }
        val rotation = image.imageInfo.rotationDegrees.toFloat()
        return transform(bitmap, rotation, mirror)
    }

    internal fun yuv420ToArgb(
        width: Int,
        height: Int,
        yPlane: ByteArray,
        yRowStride: Int,
        yPixelStride: Int,
        uPlane: ByteArray,
        uRowStride: Int,
        uPixelStride: Int,
        vPlane: ByteArray,
        vRowStride: Int,
        vPixelStride: Int,
    ): IntArray = yuv420ToArgb(
        width = width,
        height = height,
        yBuffer = ByteBuffer.wrap(yPlane),
        yRowStride = yRowStride,
        yPixelStride = yPixelStride,
        uBuffer = ByteBuffer.wrap(uPlane),
        uRowStride = uRowStride,
        uPixelStride = uPixelStride,
        vBuffer = ByteBuffer.wrap(vPlane),
        vRowStride = vRowStride,
        vPixelStride = vPixelStride,
    )

    private fun yuv420888ToArgb(image: ImageProxy): IntArray {
        val yPlane = image.planes[0]
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]
        val requiredPixels = image.width * image.height
        val pixels = argbBuffer.get()
            ?.takeIf { it.size == requiredPixels }
            ?: IntArray(requiredPixels).also { argbBuffer.set(it) }
        return yuv420ToArgb(
            width = image.width,
            height = image.height,
            yBuffer = yPlane.buffer.duplicate(),
            yRowStride = yPlane.rowStride,
            yPixelStride = yPlane.pixelStride,
            uBuffer = uPlane.buffer.duplicate(),
            uRowStride = uPlane.rowStride,
            uPixelStride = uPlane.pixelStride,
            vBuffer = vPlane.buffer.duplicate(),
            vRowStride = vPlane.rowStride,
            vPixelStride = vPlane.pixelStride,
            pixels = pixels,
        )
    }

    private fun yuv420ToArgb(
        width: Int,
        height: Int,
        yBuffer: ByteBuffer,
        yRowStride: Int,
        yPixelStride: Int,
        uBuffer: ByteBuffer,
        uRowStride: Int,
        uPixelStride: Int,
        vBuffer: ByteBuffer,
        vRowStride: Int,
        vPixelStride: Int,
        pixels: IntArray = IntArray(width * height),
    ): IntArray {
        val yStart = yBuffer.position()
        val uStart = uBuffer.position()
        val vStart = vBuffer.position()
        for (row in 0 until height) {
            for (column in 0 until width) {
                val y = yBuffer.get(yStart + row * yRowStride + column * yPixelStride).toInt() and 0xFF
                val chromaRow = row / 2
                val chromaColumn = column / 2
                val u = uBuffer.get(uStart + chromaRow * uRowStride + chromaColumn * uPixelStride).toInt() and 0xFF
                val v = vBuffer.get(vStart + chromaRow * vRowStride + chromaColumn * vPixelStride).toInt() and 0xFF
                val c = (y - 16).coerceAtLeast(0)
                val d = u - 128
                val e = v - 128
                val red = ((298 * c + 409 * e + 128) shr 8).coerceIn(0, 255)
                val green = ((298 * c - 100 * d - 208 * e + 128) shr 8).coerceIn(0, 255)
                val blue = ((298 * c + 516 * d + 128) shr 8).coerceIn(0, 255)
                pixels[row * width + column] =
                    (0xFF shl 24) or (red shl 16) or (green shl 8) or blue
            }
        }
        return pixels
    }

    private fun transform(bitmap: Bitmap, rotation: Float, mirror: Boolean): Bitmap {
        if (rotation == 0f && !mirror) return bitmap
        val matrix = Matrix().apply {
            postRotate(rotation)
            if (mirror) postScale(-1f, 1f)
        }
        val transformed = Bitmap.createBitmap(
            bitmap,
            0,
            0,
            bitmap.width,
            bitmap.height,
            matrix,
            true,
        )
        if (transformed !== bitmap) bitmap.recycle()
        return transformed
    }

    private fun elapsedMs(startedAtNanos: Long): Long =
        ((SystemClock.elapsedRealtimeNanos() - startedAtNanos) / 1_000_000L).coerceAtLeast(0L)

    private fun yuv420888ToNv21(image: ImageProxy): ByteArray {
        val width = image.width
        val height = image.height
        val output = ByteArray(width * height + width * height / 2)
        copyPlane(image.planes[0], width, height, output, 0, 1)
        val chromaHeight = height / 2
        val chromaWidth = width / 2
        val uPlane = image.planes[1]
        val vPlane = image.planes[2]
        var outputIndex = width * height
        val uBuffer = uPlane.buffer.duplicate()
        val vBuffer = vPlane.buffer.duplicate()
        val uStart = uBuffer.position()
        val vStart = vBuffer.position()
        repeat(chromaHeight) { row ->
            repeat(chromaWidth) { column ->
                val uIndex = uStart + row * uPlane.rowStride + column * uPlane.pixelStride
                val vIndex = vStart + row * vPlane.rowStride + column * vPlane.pixelStride
                output[outputIndex++] = vBuffer.get(vIndex)
                output[outputIndex++] = uBuffer.get(uIndex)
            }
        }
        return output
    }

    private fun copyPlane(
        plane: ImageProxy.PlaneProxy,
        width: Int,
        height: Int,
        output: ByteArray,
        outputOffset: Int,
        outputPixelStride: Int,
    ) {
        val buffer = plane.buffer.duplicate()
        val inputStart = buffer.position()
        var outputIndex = outputOffset
        repeat(height) { row ->
            repeat(width) { column ->
                val inputIndex =
                    inputStart + row * plane.rowStride + column * plane.pixelStride
                output[outputIndex] = buffer.get(inputIndex)
                outputIndex += outputPixelStride
            }
        }
    }
}
