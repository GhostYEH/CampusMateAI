package com.example.campusai.data.classroom.focus

import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayInputStream
import java.io.FileNotFoundException

class ClassroomAttentionModelTest {
    private val moshi = Moshi.Builder().build()
    private val mapType = Types.newParameterizedType(
        Map::class.java,
        String::class.java,
        Any::class.java,
    )
    private val adapter = moshi.adapter<Map<String, Any?>>(mapType)

    private fun golden(): Map<String, Any?> {
        val stream = javaClass.classLoader!!.getResourceAsStream(
            "classroom_attention/golden_inference.json",
        )
        assertNotNull(stream)
        return adapter.fromJson(stream!!.bufferedReader().use { it.readText() })!!
    }

    private fun map(value: Any?): Map<String, Any?> {
        @Suppress("UNCHECKED_CAST")
        return value as? Map<String, Any?> ?: emptyMap()
    }

    private fun list(value: Any?): List<Any?> =
        value as? List<Any?> ?: emptyList()

    private fun double(value: Any?): Double = (value as Number).toDouble()

    private fun int(value: Any?): Int = (value as Number).toInt()

    private fun axis(value: Any?): ClassroomAxisStats? {
        if (value == null) return null
        val raw = map(value)
        return ClassroomAxisStats(
            mean = double(raw["mean"]),
            standardDeviation = double(raw["standard_deviation"]),
            min = double(raw["min"]),
            max = double(raw["max"]),
            samples = int(raw["samples"]),
        )
    }

    private fun windowFrom(value: Any?): ClassroomObservationWindow {
        val raw = map(value)
        return ClassroomObservationWindow(
            index = int(raw["index"]),
            startOffsetMs = int(raw["start_offset_ms"]).toLong(),
            endOffsetMs = int(raw["end_offset_ms"]).toLong(),
            complete = raw["complete"] as? Boolean ?: true,
            validSampleCount = int(raw["valid_samples"]),
            invalidSampleCount = int(raw["invalid_samples"]),
            faceVisibleSampleCount = int(raw["face_visible_samples"]),
            faceVisibleRatio = double(raw["face_visible_ratio"]),
            yaw = axis(raw["yaw"]),
            pitch = axis(raw["pitch"]),
            stageCounts = map(raw["stage_counts"]).mapValues { int(it.value) },
            dominantStage = raw["dominant_stage"] as? String,
            manualPageTurns = int(raw["manual_page_turns"]),
            quizSubmissions = int(raw["quiz_submissions"]),
            questions = int(raw["questions"]),
            reasonCounts = emptyMap(),
            verdict = if (raw["verdict"] == "observable") {
                ClassroomObservationVerdict.OBSERVABLE
            } else {
                ClassroomObservationVerdict.UNOBSERVABLE
            },
            unavailableReason = (raw["unavailable_reason"] as? String)
                ?.let { ClassroomFocusReason.fromCode(it) },
        )
    }

    @Test
    fun `golden model parses as incompatible-but-valid synthetic weight`() {
        val model = golden()["model"] as Map<*, *>
        val load = ClassroomAttentionArtifactParser.parse(encode(model))
        assertTrue(load is ClassroomAttentionModelLoad.Ready)
        val artifact = (load as ClassroomAttentionModelLoad.Ready).artifact
        assertEquals(1, artifact.schemaVersion)
        assertEquals("median_impute", artifact.missingPolicy)
        assertFalse(artifact.release.eligible)
        assertTrue(artifact.featureOrder.isNotEmpty())
        assertEquals(artifact.featureOrder.size, artifact.coefficients.size)
    }

    @Test
    fun `window features and inference match python golden numbers`() {
        val payload = golden()
        val modelLoad = ClassroomAttentionArtifactParser.parse(payload["model"]?.let { encode(it) }!!)
        assertTrue(modelLoad is ClassroomAttentionModelLoad.Ready)
        val artifact = (modelLoad as ClassroomAttentionModelLoad.Ready).artifact
        val cases = list(payload["cases"])
        assertTrue(cases.isNotEmpty())
        for (case in cases) {
            val caseMap = map(case)
            val window = windowFrom(caseMap["window"])
            val expectedFeatures = map(caseMap["features"])
            val actualFeatures = ClassroomAttentionFeatures.extract(window)
            for ((name, expected) in expectedFeatures) {
                val actual = actualFeatures[name]
                if (expected == null) {
                    assertNull("feature $name for ${caseMap["name"]}", actual)
                } else {
                    assertEquals(
                        "feature $name for ${caseMap["name"]}",
                        double(expected),
                        actual!!,
                        1e-12,
                    )
                }
            }
            val scored = ClassroomAttentionInference.score(artifact, window)
            assertNotNull(scored)
            assertEquals(
                double(caseMap["expected_logit"]),
                scored!!.logit,
                1e-9,
            )
            assertEquals(
                double(caseMap["expected_probability"]),
                scored.probability,
                1e-9,
            )
            assertEquals(caseMap["expected_decision"], if (scored.offTask) "off_task" else "on_task")
            val validCoverage = actualFeatures["valid_coverage"] ?: 0.0
            val gated = ClassroomAttentionInference.predict(artifact, window)
            if (window.faceVisibleRatio >= artifact.gate.minFaceVisibleRatio &&
                validCoverage >= artifact.gate.minValidCoverage
            ) {
                assertNotNull(gated)
                assertEquals(scored.probability, gated!!.probability, 1e-9)
            } else {
                assertNull("gated ${caseMap["name"]}", gated)
            }
        }
    }

    @Test
    fun `low visibility window abstains instead of producing a prediction`() {
        val artifact = (ClassroomAttentionArtifactParser.parse(
            encode(golden()["model"]!!),
        ) as ClassroomAttentionModelLoad.Ready).artifact
        val window = ClassroomObservationWindow(
            index = 0,
            startOffsetMs = 0,
            endOffsetMs = 10_000,
            complete = true,
            validSampleCount = 40,
            invalidSampleCount = 0,
            faceVisibleSampleCount = 2,
            faceVisibleRatio = 0.05,
            yaw = null,
            pitch = null,
            stageCounts = mapOf("slide" to 40),
            dominantStage = "slide",
            manualPageTurns = 0,
            quizSubmissions = 0,
            questions = 0,
            reasonCounts = mapOf(ClassroomFocusReason.NO_FACE to 38),
            verdict = ClassroomObservationVerdict.OBSERVABLE,
            unavailableReason = null,
        )
        assertNull(ClassroomAttentionInference.predict(artifact, window))
    }

    @Test
    fun `schema version mismatch is unavailable`() {
        val model = golden()["model"] as Map<*, *>
        val incompatible = encode(model)
            .replace("\"schema_version\":1", "\"schema_version\":2")
        val load = ClassroomAttentionArtifactParser.parse(incompatible)
        assertTrue(load is ClassroomAttentionModelLoad.Unavailable)
    }

    @Test
    fun `unknown feature is unavailable`() {
        val model = golden()["model"] as Map<*, *>
        val text = encode(model).replace("face_visible_ratio", "raw_frame_hash")
        val load = ClassroomAttentionArtifactParser.parse(text)
        assertTrue(load is ClassroomAttentionModelLoad.Unavailable)
    }

    @Test
    fun `missing policy is unavailable`() {
        val model = golden()["model"] as Map<*, *>
        val text = encode(model).replace("median_impute", "nearest_neighbor")
        val load = ClassroomAttentionArtifactParser.parse(text)
        assertTrue(load is ClassroomAttentionModelLoad.Unavailable)
    }

    @Test
    fun `debug loader falls back to preview only when primary is missing`() {
        val modelText = encode(golden()["model"]!!)
        val preview = loader(
            files = mapOf("classroom_attention/model-preview.json" to modelText),
            debug = true,
        )
        assertTrue(preview.load() is ClassroomAttentionModelLoad.Ready)

        val release = loader(
            files = mapOf("classroom_attention/model-preview.json" to modelText),
            debug = false,
        )
        assertTrue(release.load() is ClassroomAttentionModelLoad.Missing)

        val primary = loader(
            files = mapOf(
                "classroom_attention/model.json" to modelText.replace(
                    "classroom-attention-synthetic-headpose",
                    "classroom-attention-real",
                ),
                "classroom_attention/model-preview.json" to modelText,
            ),
            debug = true,
        )
        assertEquals(
            "classroom-attention-real",
            (primary.load() as ClassroomAttentionModelLoad.Ready).artifact.modelVersion,
        )
    }

    @Test
    fun `malformed primary does not silently fall back to preview`() {
        val modelText = encode(golden()["model"]!!)
        val load = loader(
            files = mapOf(
                "classroom_attention/model.json" to "{broken",
                "classroom_attention/model-preview.json" to modelText,
            ),
            debug = true,
        ).load()
        assertTrue(load is ClassroomAttentionModelLoad.Unavailable)
    }

    private fun loader(files: Map<String, String>, debug: Boolean): ClassroomAttentionModelLoader =
        ClassroomAttentionModelLoader(
            openAsset = { path ->
                files[path]?.let { ByteArrayInputStream(it.toByteArray()) }
                    ?: throw FileNotFoundException(path)
            },
            debugBuild = debug,
        )

    @Test
    fun `empty or truncated payload falls back without throwing`() {
        assertTrue(ClassroomAttentionArtifactParser.parse("") is ClassroomAttentionModelLoad.Unavailable)
        assertTrue(
            ClassroomAttentionArtifactParser.parse("{\"schema_version\":1") is
                ClassroomAttentionModelLoad.Unavailable,
        )
    }

    @Test
    fun `coefficient count must match feature order`() {
        val model = golden()["model"] as Map<*, *>
        val coefficients = (model["coefficients"] as List<*>).dropLast(1)
        @Suppress("UNCHECKED_CAST")
        val patched = (model as Map<String, Any?>) + ("coefficients" to coefficients)
        val text = encode(patched)
        val load = ClassroomAttentionArtifactParser.parse(text)
        assertTrue(load is ClassroomAttentionModelLoad.Unavailable)
    }

    private fun encode(value: Any?): String {
        val adapterAny = moshi.adapter<Any>(Any::class.java)
        return adapterAny.toJson(value)
    }
}
