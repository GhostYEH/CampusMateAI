package com.example.campusai.data.behavior

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class BehaviorRoiTest {

    @Test
    fun expandsPersonBoxAndClampsItToBitmapBounds() {
        val roi = BehaviorRoi.from(
            left = -5f,
            top = 10f,
            right = 95f,
            bottom = 90f,
            imageWidth = 100,
            imageHeight = 100,
            paddingFraction = 0.10f,
        )

        assertEquals(0, roi?.left)
        assertEquals(2, roi?.top)
        assertEquals(100, roi?.right)
        assertEquals(98, roi?.bottom)
    }

    @Test
    fun rejectsDegeneratePersonBox() {
        assertNull(
            BehaviorRoi.from(
                left = 20f,
                top = 20f,
                right = 20f,
                bottom = 50f,
                imageWidth = 100,
                imageHeight = 100,
            ),
        )
    }
}

