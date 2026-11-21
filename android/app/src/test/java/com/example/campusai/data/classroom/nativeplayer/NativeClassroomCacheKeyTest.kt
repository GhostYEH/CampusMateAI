package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertNull
import org.junit.Test

class NativeClassroomCacheKeyTest {

    @Test
    fun `cache key isolates service account classroom and revision`() {
        val base = NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course", "workspace", "stage", 1)
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-b", "user-a", "course", "workspace", "stage", 1))
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-b", "course", "workspace", "stage", 1))
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course-2", "workspace", "stage", 1))
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course", "workspace-2", "stage", 1))
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course", "workspace", "stage-2", 1))
        assertNotEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course", "workspace", "stage", 2))
        assertEquals(base, NativeClassroomCacheKey.cacheKey("svc-a", "user-a", "course", "workspace", "stage", 1))
    }

    @Test
    fun `asset policy resolves only addressable refs`() {
        val api = "https://api.example.com/api/v1/"
        assertEquals("https://cdn.example.com/a.png", NativeClassroomAssetPolicy.resolve("https://cdn.example.com/a.png", api))
        assertEquals("https://api.example.com/assets/a.png", NativeClassroomAssetPolicy.resolve("/assets/a.png", api))
        assertEquals("https://api.example.com/assets/a.png", NativeClassroomAssetPolicy.resolve("assets/a.png", api))
        assertEquals("https://cdn.example.com/a.png", NativeClassroomAssetPolicy.resolve("//cdn.example.com/a.png", api))
        assertNull(NativeClassroomAssetPolicy.resolve("asset:opaque-id", api))
        assertNull(NativeClassroomAssetPolicy.resolve("opaque-id", api))
    }
}
