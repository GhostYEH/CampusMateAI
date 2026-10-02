package com.example.campusai.data.behavior

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.ByteArrayInputStream
import java.io.File

class BehaviorModelAssetCacheTest {
    @get:Rule val temporaryFolder = TemporaryFolder()

    @Test
    fun assetUpgradeUsesNewCopyAndPreservesLegacyAndPreviousCaches() {
        val directory = temporaryFolder.newFolder()
        val legacy = File(directory, "model.onnx").apply { writeBytes(byteArrayOf(9)) }
        val first = BehaviorModelAssetCache.ensureFile(directory, "model.onnx") {
            ByteArrayInputStream(byteArrayOf(1, 2))
        }
        val second = BehaviorModelAssetCache.ensureFile(directory, "model.onnx") {
            ByteArrayInputStream(byteArrayOf(3, 4))
        }
        assertNotEquals(first, second)
        assertArrayEquals(byteArrayOf(1, 2), first.readBytes())
        assertArrayEquals(byteArrayOf(3, 4), second.readBytes())
        assertArrayEquals(byteArrayOf(9), legacy.readBytes())
    }

    @Test
    fun verifiesExistingCacheAndRepairsSameSizeCorruption() {
        val directory = temporaryFolder.newFolder()
        val bytes = byteArrayOf(1, 2, 3)
        val original = BehaviorModelAssetCache.ensureFile(directory, "model.onnx") { ByteArrayInputStream(bytes) }
        original.writeBytes(byteArrayOf(4, 5, 6))
        val repaired = BehaviorModelAssetCache.ensureFile(directory, "model.onnx") { ByteArrayInputStream(bytes) }
        assertEquals(original, repaired)
        assertArrayEquals(bytes, repaired.readBytes())
    }

    @Test
    fun interruptedAssetCopyKeepsPreviouslyVerifiedModel() {
        val directory = temporaryFolder.newFolder()
        val previous = BehaviorModelAssetCache.ensureFile(directory, "model.onnx") {
            ByteArrayInputStream(byteArrayOf(1, 2))
        }
        var opens = 0
        val attempt = runCatching {
            BehaviorModelAssetCache.ensureFile(directory, "model.onnx") {
                opens++
                if (opens == 2) error("synthetic asset read failure")
                ByteArrayInputStream(byteArrayOf(3, 4))
            }
        }
        assertTrue(attempt.isFailure)
        assertArrayEquals(byteArrayOf(1, 2), previous.readBytes())
        assertTrue(directory.listFiles().orEmpty().none { it.name.endsWith(".tmp") })
    }
}
