package com.example.campusai.data.classroom.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Test

class NativePlaybackPolicyTest {

    @Test
    fun `native needs document and content`() {
        assertEquals(
            NativeSceneMode.NATIVE,
            NativePlaybackPolicy.decide(NativeRenderKind.NATIVE, "slide", true, true, false).mode,
        )
        assertEquals(
            NativeSceneMode.UNAVAILABLE,
            NativePlaybackPolicy.decide(NativeRenderKind.NATIVE, "slide", false, true, true).mode,
        )
        assertEquals(
            NativeSceneMode.UNAVAILABLE,
            NativePlaybackPolicy.decide(NativeRenderKind.NATIVE, "interactive", true, true, true).mode,
        )
    }

    @Test
    fun `sandbox url uses its own payload instead of fallback availability`() {
        assertEquals(
            NativeSceneMode.SANDBOX_URL,
            NativePlaybackPolicy.decide(NativeRenderKind.SANDBOX_URL, "interactive", true, true, false).mode,
        )
        assertEquals(
            NativeSceneMode.WEB_FALLBACK,
            NativePlaybackPolicy.decide(NativeRenderKind.SANDBOX_URL, "interactive", true, false, true).mode,
        )
        assertEquals(
            NativeSceneMode.UNAVAILABLE,
            NativePlaybackPolicy.decide(NativeRenderKind.SANDBOX_URL, "interactive", true, false, false).mode,
        )
    }

    @Test
    fun `unsupported uses fallback only when available`() {
        val fallback = NativePlaybackPolicy.decide(
            NativeRenderKind.UNSUPPORTED, "slide", true, true, true, "render_unsupported",
        )
        assertEquals(NativeSceneMode.WEB_FALLBACK, fallback.mode)
        assertEquals("render_unsupported", fallback.reason)

        val unavailable = NativePlaybackPolicy.decide(
            NativeRenderKind.MISSING, "slide", true, true, false,
        )
        assertEquals(NativeSceneMode.UNAVAILABLE, unavailable.mode)
    }

    @Test
    fun `sandbox html needs payload`() {
        assertEquals(
            NativeSceneMode.SANDBOX_HTML,
            NativePlaybackPolicy.decide(NativeRenderKind.SANDBOX_HTML, "interactive", true, true, false).mode,
        )
        assertEquals(
            NativeSceneMode.UNAVAILABLE,
            NativePlaybackPolicy.decide(NativeRenderKind.SANDBOX_HTML, "interactive", true, false, false).mode,
        )
    }
}
