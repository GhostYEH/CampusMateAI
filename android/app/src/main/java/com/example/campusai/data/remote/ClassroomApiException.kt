package com.example.campusai.data.remote

/**
 * 课堂接口带 HTTP 状态码的失败，供客户端区分 409 冲突等可回读状态。
 * 消息保持面向用户的原始文案，不携带 URL 或凭证。
 */
class ClassroomApiException(
    val statusCode: Int,
    val code: String? = null,
    override val message: String,
) : Exception(message)
