package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ClassroomMediaPolicyTest {

    private val api = "https://api.example.com/api/v1/"
    private val classic = NativeClassroomRef(
        courseId = "course-1",
        workspaceId = "",
        stageId = "session-1",
        sessionId = "session-1",
        source = NativeClassroomSource.COURSE_CLASSIC,
    )

    @Test
    fun `trusted classroom media carries credentials only for current classroom path`() {
        val mediaBase = ClassroomMediaPolicy.mediaBasePath(api, classic)
        assertEquals(
            "/api/v1/courses/course-1/interactive-classroom/session-1/media",
            mediaBase,
        )
        val url = api.removeSuffix("/") +
            "/courses/course-1/interactive-classroom/session-1/media/media/img-1.png"
        assertTrue(ClassroomMediaPolicy.isTrusted(url, api, classic))
        assertFalse(
            ClassroomMediaPolicy.isTrusted(
                api + "courses/course-2/interactive-classroom/session-1/media/media/img-1.png",
                api,
                classic,
            ),
        )
        assertFalse(
            ClassroomMediaPolicy.isTrusted(
                api + "courses/course-1/interactive-classroom/session-2/media/media/img-1.png",
                api,
                classic,
            ),
        )
    }

    @Test
    fun `credential helper only returns bearer for trusted current classroom media`() {
        val url = api.removeSuffix("/") +
            "/courses/course-1/interactive-classroom/session-1/media/media/img-1.png"
        assertEquals(
            "Bearer token-1",
            ClassroomMediaPolicy.authorizationHeader(url, api, classic, "token-1"),
        )
        assertNull(
            ClassroomMediaPolicy.authorizationHeader("https://cdn.example.com/a.png", api, classic, "token-1"),
        )
        assertNull(
            ClassroomMediaPolicy.authorizationHeader(
                api + "courses/course-2/interactive-classroom/session-1/media/media/img-1.png",
                api,
                classic,
                "token-1",
            ),
        )
        assertNull(ClassroomMediaPolicy.authorizationHeader(url, api, classic, null))
        assertNull(
            ClassroomMediaPolicy.authorizationHeader(
                api + "courses/course-1/login",
                api,
                classic,
                "token-1",
            ),
        )
    }

    @Test
    fun `external media keeps address but never receives bearer scope`() {
        val target = ClassroomMediaPolicy.resolve("https://cdn.example.com/a.png", api, classic)
        assertEquals("https://cdn.example.com/a.png", target?.url)
        assertFalse(target?.trusted ?: true)
        assertFalse(ClassroomMediaPolicy.isTrusted("https://cdn.example.com/a.png", api, classic))
        assertFalse(
            ClassroomMediaPolicy.isTrusted(
                "https://api.example.com.evil.example/courses/course-1/interactive-classroom/session-1/media/media/a.png",
                api,
                classic,
            ),
        )
    }

    @Test
    fun `relative media ref keeps duplicated media segment and api base prefix`() {
        val mediaBase = ClassroomMediaPolicy.mediaBasePath(api, classic)
        val relative = ClassroomMediaPolicy.resolve("media/img-1.png", api, classic)
        assertEquals(
            "https://api.example.com/api/v1/courses/course-1/interactive-classroom/session-1/media/media/img-1.png",
            relative?.url,
        )
        assertTrue(relative?.trusted == true)

        val absoluteRelative = ClassroomMediaPolicy.resolve(
            "/api/v1/courses/course-1/interactive-classroom/session-1/media/audio/narration.mp3",
            api,
            classic,
        )
        assertEquals(
            "https://api.example.com/api/v1/courses/course-1/interactive-classroom/session-1/media/audio/narration.mp3",
            absoluteRelative?.url,
        )
        assertTrue(absoluteRelative?.trusted == true)
        assertEquals(
            "https://api.example.com/api/v1/courses/course-1/interactive-classroom/session-1/media/media/img-1.png",
            NativeClassroomAssetPolicy.resolve("media/img-1.png", api, mediaBase),
        )
    }

    @Test
    fun `self classroom uses self media route and still isolates other sessions`() {
        val self = NativeClassroomRef(
            courseId = "",
            workspaceId = "",
            stageId = "self-1",
            sessionId = "self-1",
            source = NativeClassroomSource.SELF_CLASSIC,
        )
        assertEquals(
            "/api/v1/self-classroom/self-1/media",
            ClassroomMediaPolicy.mediaBasePath(api, self),
        )
        assertTrue(
            ClassroomMediaPolicy.isTrusted(
                api + "self-classroom/self-1/media/media/a.png",
                api,
                self,
            ),
        )
        assertFalse(
            ClassroomMediaPolicy.isTrusted(
                api + "self-classroom/self-2/media/media/a.png",
                api,
                self,
            ),
        )
    }

    @Test
    fun `redirect target must stay on the trusted api origin`() {
        assertTrue(ClassroomMediaPolicy.isSameApiOrigin(api + "courses/course-1/x", api))
        assertFalse(ClassroomMediaPolicy.isSameApiOrigin("http://api.example.com/api/v1/x", api))
        assertFalse(ClassroomMediaPolicy.isSameApiOrigin("https://api.example.com:444/api/v1/x", api))
        assertFalse(ClassroomMediaPolicy.isSameApiOrigin("https://evil.example.com/api/v1/x", api))
        assertFalse(ClassroomMediaPolicy.isSameApiOrigin("https://api.example.com.evil.com/x", api))
    }

    @Test
    fun `late media response is rejected after account or classroom switch`() {
        val session = ClassroomMediaSession("account-a", classic)
        val generation = session.beginRequest()
        assertTrue(session.isCurrent(generation, "account-a", classic))
        assertFalse(session.isCurrent(generation, "account-b", classic))
        assertFalse(
            session.isCurrent(
                generation,
                "account-a",
                classic.copy(stageId = "session-2", sessionId = "session-2"),
            ),
        )
        session.invalidate()
        assertFalse(session.isCurrent(generation, "account-a", classic))
    }
}
