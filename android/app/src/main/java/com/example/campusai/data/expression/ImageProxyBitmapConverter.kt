package com.example.campusai.data.expression

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Matrix
import android.graphics.Rect
import android.graphics.YuvImage
import androidx.camera.core.ImageProxy
import java.io.ByteArrayOutputStream

object ImageProxyBitmapConverter {
    fun toUprightMirroredBitmap(image: ImageProxy, mirror: Boolean): Bitmap {
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
