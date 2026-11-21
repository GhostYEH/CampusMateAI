package com.example.campusai.data.classroom.nativeplayer

import android.net.Uri
import androidx.media3.common.C
import androidx.media3.common.PlaybackException
import androidx.media3.datasource.BaseDataSource
import androidx.media3.datasource.DataSource
import androidx.media3.datasource.DataSourceException
import androidx.media3.datasource.DataSpec
import java.io.IOException
import java.io.InputStream
import kotlin.math.min
import okhttp3.OkHttpClient
import okhttp3.Request

/**
 * Media3 的课堂媒体 DataSource。
 *
 * 用共享的课堂媒体 OkHttp 客户端发请求：可信本站媒体自动带 Bearer，401 走同一套刷新；
 * 手动处理重定向，跨服务域的 Location 直接失败，绝不把 Authorization 带到外域。
 */
class ClassroomMediaDataSourceFactory(
    private val client: OkHttpClient,
    private val ref: NativeClassroomRef,
    private val apiBaseUrl: String,
) : DataSource.Factory {
    override fun createDataSource(): DataSource =
        ClassroomMediaDataSource(client, ref, apiBaseUrl)
}

private class ClassroomMediaDataSource(
    private val client: OkHttpClient,
    private val ref: NativeClassroomRef,
    private val apiBaseUrl: String,
) : BaseDataSource(true) {

    private var response: okhttp3.Response? = null
    private var input: InputStream? = null
    private var openedUri: Uri? = null
    private var bytesRemaining = C.LENGTH_UNSET.toLong()
    private var opened = false

    override fun open(dataSpec: DataSpec): Long {
        close()
        bytesRemaining = C.LENGTH_UNSET.toLong()
        openedUri = null
        transferInitializing(dataSpec)
        val scheme = dataSpec.uri.scheme.orEmpty()
        if (scheme != "http" && scheme != "https") {
            throw IOException("课堂媒体只支持 HTTP(S) 地址")
        }
        if (!ClassroomMediaPolicy.isSameApiOrigin(dataSpec.uri.toString(), apiBaseUrl)) {
            throw IOException("课堂媒体地址不在当前服务域内")
        }
        var request = buildRequest(dataSpec)
        var redirects = 0
        while (true) {
            val call = client.newCall(request)
            val result = call.execute()
            if (result.code in 300..399) {
                val location = result.header("Location")
                val previous = request
                result.close()
                if (location.isNullOrBlank()) throw IOException("课堂媒体重定向缺少 Location")
                if (redirects++ >= 5) throw IOException("课堂媒体重定向次数过多")
                val target = previous.url.resolve(location) ?: throw IOException("课堂媒体重定向地址无效")
                if (!ClassroomMediaPolicy.isSameApiOrigin(target.toString(), apiBaseUrl)) {
                    throw IOException("课堂媒体重定向到非可信域，已停止请求")
                }
                request = previous.newBuilder().url(target).build()
                continue
            }
            if (result.code == 416) {
                result.close()
                throw DataSourceException(PlaybackException.ERROR_CODE_IO_READ_POSITION_OUT_OF_RANGE)
            }
            if (result.code !in 200..299) {
                val detail = result.body?.string()?.take(160).orEmpty()
                result.close()
                throw IOException("课堂媒体请求失败 (${result.code}) $detail")
            }
            response = result
            openedUri = Uri.parse(result.request.url.toString())
            input = result.body?.byteStream()
            opened = true
            val contentLength = result.body?.contentLength() ?: C.LENGTH_UNSET.toLong()
            if (result.code != 206 && dataSpec.position > 0L) {
                skipFully(dataSpec.position)
            }
            bytesRemaining = when {
                dataSpec.length != C.LENGTH_UNSET.toLong() -> dataSpec.length
                result.code == 206 -> contentLength
                dataSpec.position > 0L && contentLength != C.LENGTH_UNSET.toLong() ->
                    (contentLength - dataSpec.position).coerceAtLeast(0)
                else -> contentLength
            }
            transferStarted(dataSpec)
            return if (bytesRemaining == C.LENGTH_UNSET.toLong()) C.LENGTH_UNSET.toLong() else bytesRemaining
        }
    }

    private fun buildRequest(dataSpec: DataSpec): Request {
        val builder = Request.Builder()
            .url(dataSpec.uri.toString())
            .get()
        dataSpec.httpRequestHeaders.forEach { (name, value) -> builder.header(name, value) }
        if (dataSpec.position > 0L || dataSpec.length != C.LENGTH_UNSET.toLong()) {
            val rangeEnd = if (dataSpec.length == C.LENGTH_UNSET.toLong()) {
                ""
            } else {
                (dataSpec.position + dataSpec.length - 1).toString()
            }
            builder.header("Range", "bytes=${dataSpec.position}-$rangeEnd")
        }
        return builder.build()
    }

    private fun skipFully(position: Long) {
        val stream = input ?: throw IOException("课堂媒体流尚未打开")
        val buffer = ByteArray(8 * 1024)
        var remaining = position
        while (remaining > 0L) {
            val read = stream.read(buffer, 0, min(buffer.size.toLong(), remaining).toInt())
            if (read == -1) throw IOException("课堂媒体起点超出资源长度")
            remaining -= read
        }
    }

    override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
        if (length == 0) return 0
        if (bytesRemaining == 0L) return C.RESULT_END_OF_INPUT
        val stream = input ?: return C.RESULT_END_OF_INPUT
        val maxRead = if (bytesRemaining == C.LENGTH_UNSET.toLong()) {
            length
        } else {
            min(length.toLong(), bytesRemaining).toInt()
        }
        val read = stream.read(buffer, offset, maxRead)
        if (read == -1) return C.RESULT_END_OF_INPUT
        if (bytesRemaining != C.LENGTH_UNSET.toLong()) bytesRemaining -= read
        bytesTransferred(read)
        return read
    }

    override fun close() {
        try {
            input?.close()
        } catch (_: IOException) {
            // 关闭失败不覆盖播放器真正关心的读取错误。
        } finally {
            input = null
        }
        response?.close()
        response = null
        if (opened) {
            opened = false
            transferEnded()
        }
        openedUri = null
    }

    override fun getUri(): Uri? = openedUri

    override fun getResponseHeaders(): Map<String, List<String>> =
        response?.headers?.toMultimap()?.mapKeys { it.key.lowercase() }.orEmpty()

    fun getResponseCode(): Int = response?.code ?: 0

    fun getContentType(): String? = response?.body?.contentType()?.toString()
}
