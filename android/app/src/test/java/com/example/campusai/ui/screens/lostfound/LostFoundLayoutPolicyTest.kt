package com.example.campusai.ui.screens.lostfound

import org.junit.Assert.assertEquals
import org.junit.Test

class LostFoundLayoutPolicyTest {
    @Test
    fun compactPhonesUseNarrowerCategoryChipPadding() {
        assertEquals(9f, lostFoundCategoryChipHorizontalPaddingDp(screenWidthDp = 432))
    }

    @Test
    fun widerPhonesKeepComfortableCategoryChipPadding() {
        assertEquals(12f, lostFoundCategoryChipHorizontalPaddingDp(screenWidthDp = 433))
    }
}
