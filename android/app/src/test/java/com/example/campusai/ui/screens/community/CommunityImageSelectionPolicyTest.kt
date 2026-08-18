package com.example.campusai.ui.screens.community

import org.junit.Assert.assertEquals
import org.junit.Test

class CommunityImageSelectionPolicyTest {
    @Test
    fun imagePickerOnlyUsesRemainingSlots() {
        assertEquals(2, uploadableCommunityImageCount(currentCount = 7, pickedCount = 5))
    }

    @Test
    fun imagePickerDoesNotUploadWhenLimitIsReached() {
        assertEquals(0, uploadableCommunityImageCount(currentCount = 9, pickedCount = 1))
    }
}
