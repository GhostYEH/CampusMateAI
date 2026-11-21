package com.example.campusai.data.classroom.nativeplayer

import java.security.MessageDigest

/** 纯 JVM 的缓存键，便于在没有 Android/Coil 环境时回归服务与账号隔离。 */
object NativeClassroomCacheKey {
    fun digest(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray(Charsets.UTF_8))
        .joinToString("") { "%02x".format(it.toInt() and 0xff) }

    fun cacheKey(
        service: String,
        account: String,
        courseId: String,
        workspaceId: String,
        stageId: String,
        revision: Int,
    ): String = digest("$service|$account|$courseId|$workspaceId|$stageId|$revision")
}

/**
 * 图片/视频地址解析。只接受 http(s) 或文档内的相对路径；不透明 AssetRef 无法
 * 在客户端解析，交给界面显示"资源未下发"，不冒充图片。
 *
 * 传入当前课堂的媒体接口前缀时，`media/...` 与裸文件名会补成
 * `/api/v1/.../media/media/...`，保留契约要求的重复 media 段。
 */
object NativeClassroomAssetPolicy {
    fun resolve(source: String?, apiBaseUrl: String): String? =
        resolve(source, apiBaseUrl, mediaBasePath = null)

    fun resolve(source: String?, apiBaseUrl: String, mediaBasePath: String?): String? =
        ClassroomMediaPolicy.resolve(source, apiBaseUrl, mediaBasePath)?.url
}
