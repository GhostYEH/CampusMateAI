package com.example.campusai.data.classroom.nativeplayer

import android.content.Context
import coil.ImageLoader
import coil.disk.DiskCache
import coil.memory.MemoryCache
import com.example.campusai.BuildConfig
import com.example.campusai.data.remote.ApiClient
import com.example.campusai.data.remote.ClassroomPlaybackDto
import com.example.campusai.data.remote.MagicClassStagePlaybackDto
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.io.File

/**
 * 课堂缓存按「服务｜账号｜课程/工作台/舞台」隔离，文档与讲解再按 revision 分文件。
 * 这样换账号、换课堂或课堂版本更新都不会读到上一份内容；旧版本只保留最近三份。
 */
class NativeClassroomCache(
    context: Context,
    accountScope: String,
    private val ref: NativeClassroomRef,
) {
    private val appContext = context.applicationContext
    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
    private val documentAdapter = moshi.adapter<Map<String, Any?>>(
        Types.newParameterizedType(Map::class.java, String::class.java, Any::class.java),
    )
    private val playbackAdapter = moshi.adapter(MagicClassStagePlaybackDto::class.java)
    private val classicPlaybackAdapter = moshi.adapter(ClassroomPlaybackDto::class.java)

    private val root: File = File(
        File(appContext.cacheDir, "classroom-native"),
        "magicclass-" + NativeClassroomCacheKey.digest(
            "${BuildConfig.API_BASE_URL}|$accountScope|${ref.stableKey}",
        ).take(20),
    )

    val imageLoader: ImageLoader by lazy {
        ImageLoader.Builder(appContext)
            .memoryCache {
                MemoryCache.Builder(appContext)
                    .maxSizeBytes(32 * 1024 * 1024)
                    .build()
            }
            .diskCache {
                DiskCache.Builder()
                    .directory(File(root, "images"))
                    .maxSizeBytes(64L * 1024L * 1024L)
                    .build()
            }
            // 经典课堂媒体走 API 同源鉴权：只有当前课堂 media|audio 路径带 Bearer。
            .okHttpClient(ApiClient.classroomMediaHttpClient(ref))
            .crossfade(false)
            .build()
    }

    private val stageFile: File get() = File(root, "stage.json")
    private val metaFile: File get() = File(root, "stage-meta.json")
    private val playbackFile: File get() = File(root, "playback.json")
    private val classicPlaybackFile: File get() = File(root, "classic-playback.json")

    fun readStage(): Map<String, Any?>? {
        if (!stageFile.isFile) return null
        return runCatching {
            documentAdapter.fromJson(stageFile.readText(Charsets.UTF_8))
        }.getOrNull()
    }

    fun readRevision(): Int {
        if (!metaFile.isFile) return 0
        return runCatching {
            org.json.JSONObject(metaFile.readText(Charsets.UTF_8)).optInt("revision", 0)
        }.getOrDefault(0)
    }

    fun readPlayback(): MagicClassStagePlaybackDto? {
        if (!playbackFile.isFile) return null
        return runCatching {
            playbackAdapter.fromJson(playbackFile.readText(Charsets.UTF_8))
        }.getOrNull()
    }

    fun readClassicPlayback(): ClassroomPlaybackDto? {
        if (!classicPlaybackFile.isFile) return null
        return runCatching {
            classicPlaybackAdapter.fromJson(classicPlaybackFile.readText(Charsets.UTF_8))
        }.getOrNull()
    }

    fun writeStage(revision: Int, document: Map<String, Any?>) {
        runCatching {
            root.mkdirs()
            val json = documentAdapter.toJson(document) ?: return
            val versionFile = File(root, "stage-$revision.json")
            versionFile.writeText(json, Charsets.UTF_8)
            stageFile.writeText(json, Charsets.UTF_8)
            metaFile.writeText(org.json.JSONObject().put("revision", revision).toString(), Charsets.UTF_8)
            trimVersions("stage-", keep = 3)
        }
    }

    fun writePlayback(playback: MagicClassStagePlaybackDto) {
        runCatching {
            root.mkdirs()
            playbackAdapter.toJson(playback)?.let { playbackFile.writeText(it, Charsets.UTF_8) }
        }
    }

    fun writeClassicPlayback(playback: ClassroomPlaybackDto) {
        runCatching {
            root.mkdirs()
            classicPlaybackAdapter.toJson(playback)?.let { classicPlaybackFile.writeText(it, Charsets.UTF_8) }
        }
    }

    fun audioFile(artifactId: String, revision: Int, extension: String = "audio"): File =
        File(root, "narration-$revision-${NativeClassroomCacheKey.digest(artifactId).take(16)}.$extension")

    fun readAudio(artifactId: String, revision: Int): File? {
        val prefix = "narration-$revision-${NativeClassroomCacheKey.digest(artifactId).take(16)}."
        return root.listFiles()
            ?.firstOrNull { it.isFile && it.name.startsWith(prefix) && it.length() > 0 && !it.name.endsWith(".tmp") }
    }

    fun writeAudio(artifactId: String, revision: Int, bytes: ByteArray): File? {
        return runCatching {
            root.mkdirs()
            val file = audioFile(artifactId, revision, audioExtension(bytes))
            val temp = File(root, "${file.name}.tmp")
            temp.writeBytes(bytes)
            if (file.exists()) file.delete()
            if (!temp.renameTo(file)) {
                temp.copyTo(file, overwrite = true)
                temp.delete()
            }
            trimVersions("narration-", keep = 6)
            file
        }.getOrNull()
    }

    /** Media3 会按扩展名推断容器；按音频头选择真实后缀，避免 `.audio` 被当成未知文件。 */
    private fun audioExtension(bytes: ByteArray): String {
        val head = bytes.take(12)
        return when {
            head.size >= 3 && head[0] == 'I'.code.toByte() && head[1] == 'D'.code.toByte() && head[2] == '3'.code.toByte() -> "mp3"
            head.size >= 4 && head[0].toInt() == 0xFF && (head[1].toInt() and 0xE0) == 0xE0 -> "mp3"
            head.size >= 4 && head[0] == 'R'.code.toByte() && head[1] == 'I'.code.toByte() &&
                head[2] == 'F'.code.toByte() && head[3] == 'F'.code.toByte() -> "wav"
            head.size >= 4 && head[0] == 'O'.code.toByte() && head[1] == 'g'.code.toByte() &&
                head[2] == 'g'.code.toByte() && head[3] == 'S'.code.toByte() -> "ogg"
            head.size >= 8 && head[4] == 'f'.code.toByte() && head[5] == 't'.code.toByte() &&
                head[6] == 'y'.code.toByte() && head[7] == 'p'.code.toByte() -> "m4a"
            else -> "audio"
        }
    }

    fun trimVersions(prefix: String, keep: Int) {
        val versions = root.listFiles()
            ?.filter { it.isFile && it.name.startsWith(prefix) && !it.name.endsWith(".tmp") }
            ?.sortedByDescending { it.lastModified() }
            .orEmpty()
        versions.drop(keep).forEach { it.delete() }
    }

    fun clear() {
        runCatching { root.deleteRecursively() }
    }

}
