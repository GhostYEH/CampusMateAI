package com.example.campusai.data.behavior

import java.io.File
import java.io.InputStream
import java.security.MessageDigest

/** Content-addressed model copies keep asset upgrades separate from older cached weights. */
internal object BehaviorModelAssetCache {
    fun ensureFile(directory: File, filename: String, openAsset: () -> InputStream): File {
        if (!directory.isDirectory && !directory.mkdirs()) error("Could not create model cache")
        val expectedHash = openAsset().use(::sha256)
        val modelFile = File(directory, "${filename.substringBeforeLast('.')}-$expectedHash.onnx")
        if (modelFile.isFile && modelFile.inputStream().use(::sha256) == expectedHash) return modelFile

        val temporary = File(directory, "${modelFile.name}.tmp")
        try {
            openAsset().use { input -> temporary.outputStream().use { output -> input.copyTo(output) } }
            check(temporary.inputStream().use(::sha256) == expectedHash) { "Model asset copy failed verification" }
            if (!temporary.renameTo(modelFile)) temporary.copyTo(modelFile, overwrite = true)
            return modelFile
        } finally {
            temporary.delete()
        }
    }

    private fun sha256(input: InputStream): String {
        val digest = MessageDigest.getInstance("SHA-256")
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            digest.update(buffer, 0, count)
        }
        return digest.digest().joinToString("") { "%02x".format(it.toInt() and 0xff) }
    }
}
