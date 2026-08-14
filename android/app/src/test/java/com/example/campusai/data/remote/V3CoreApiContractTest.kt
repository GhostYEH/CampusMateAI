package com.example.campusai.data.remote

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class V3CoreApiContractTest {
    @Test
    fun `university selection uses backend identifier`() {
        assertEquals("university-demo", UniversitySelectionRequest("university-demo").university_id)
    }

    @Test
    fun `community post defaults to named campus post`() {
        val request = CommunityPostCreateRequest(title = "约自习", content = "图书馆见")
        assertEquals("campus", request.category)
        assertFalse(request.is_anonymous)
        assertEquals(emptyList<String>(), request.images)
    }
}
