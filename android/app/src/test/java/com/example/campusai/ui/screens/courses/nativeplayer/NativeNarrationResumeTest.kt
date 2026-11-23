package com.example.campusai.ui.screens.courses.nativeplayer

import org.junit.Assert.assertEquals
import org.junit.Test

class NativeNarrationResumeTest {

    @Test
    fun `another scene requires a fresh query`() {
        val state = NativeNarrationUiState(sceneId = "scene-b", jobId = "job-1", jobStatus = "running")
        assertEquals(NarrationResumeAction.Query, narrationResumeAction(state, "scene-a"))
    }

    @Test
    fun `cached audio is reused without a request`() {
        val state = NativeNarrationUiState(
            sceneId = "scene-a",
            artifactId = "artifact-1",
            audioFile = java.io.File("/tmp/narration.mp3"),
        )
        assertEquals(NarrationResumeAction.None, narrationResumeAction(state, "scene-a"))
    }

    @Test
    fun `completed artifact only needs download`() {
        val state = NativeNarrationUiState(
            sceneId = "scene-a",
            jobId = "job-1",
            jobStatus = "completed",
            artifactId = "artifact-1",
        )
        assertEquals(NarrationResumeAction.Download, narrationResumeAction(state, "scene-a"))
    }

    @Test
    fun `queued or running job resumes polling`() {
        val running = NativeNarrationUiState(
            sceneId = "scene-a",
            jobId = "job-1",
            jobStatus = "running",
        )
        assertEquals(NarrationResumeAction.Poll, narrationResumeAction(running, "scene-a"))

        val queued = running.copy(jobStatus = "queued")
        assertEquals(NarrationResumeAction.Poll, narrationResumeAction(queued, "scene-a"))
    }

    @Test
    fun `finished or failed state falls back to query`() {
        val finished = NativeNarrationUiState(
            sceneId = "scene-a",
            jobId = "job-1",
            jobStatus = "completed",
        )
        assertEquals(NarrationResumeAction.Query, narrationResumeAction(finished, "scene-a"))

        val failed = finished.copy(jobStatus = "failed", error = "生成失败")
        assertEquals(NarrationResumeAction.Query, narrationResumeAction(failed, "scene-a"))
    }
}
