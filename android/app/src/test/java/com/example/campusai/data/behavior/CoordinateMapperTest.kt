package com.example.campusai.data.behavior

import android.graphics.RectF
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner

@RunWith(RobolectricTestRunner::class)
class CoordinateMapperTest {

    @Test
    fun mapsCameraCoordinatesToModelInputCoordinates() {
        val mapped = CoordinateMapper.mapRect(
            sourceRect = RectF(160f, 120f, 480f, 360f),
            sourceWidth = 640,
            sourceHeight = 480,
            targetWidth = 224,
            targetHeight = 224,
        )

        requireNotNull(mapped)
        assertEquals(56f, mapped.left)
        assertEquals(56f, mapped.top)
        assertEquals(168f, mapped.right)
        assertEquals(168f, mapped.bottom)
    }

    @Test
    fun rejectsEmptyOrInvalidMappedRegions() {
        assertNull(
            CoordinateMapper.mapRect(
                sourceRect = RectF(30f, 40f, 30f, 100f),
                sourceWidth = 640,
                sourceHeight = 480,
                targetWidth = 224,
                targetHeight = 224,
            ),
        )
    }
}
