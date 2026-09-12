package com.example.campusai.data.remote.agent

import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import okhttp3.ResponseBody
import retrofit2.Response
import java.security.MessageDigest
import java.util.UUID

/**
 * 稳定 Idempotency-Key 生成器。
 *
 * 重组屏幕、旋转或重试不得重复创建：同一逻辑操作（同账号 + 同 payload 摘要）
 * 生成相同 key。完全随机的 UUID 仅用于无自然键的临时操作。
 */
object AgentIdempotency {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()

    fun stableKey(vararg parts: String): String {
        val joined = parts.joinToString("|")
        val digest = MessageDigest.getInstance("SHA-256").digest(joined.toByteArray(Charsets.UTF_8))
        return digest.fold(StringBuilder()) { acc, b -> acc.append("%02x".format(b)) }.toString()
    }

    fun payloadKey(userId: String, operation: String, payload: Any): String {
        val json = runCatching {
            moshi.adapter(Any::class.java).toJson(payload)
        }.getOrDefault(payload.toString())
        return stableKey(userId, operation, json)
    }

    fun random(): String = UUID.randomUUID().toString()
}

/**
 * 统一错误 envelope 解析。
 *
 * 客户端分支于 code 做业务行为，从不解析 message。
 */
object AgentErrorParser {
    private val moshi = Moshi.Builder().addLast(KotlinJsonAdapterFactory()).build()
    private val adapter = moshi.adapter(AgentErrorEnvelope::class.java)

    fun parse(body: ResponseBody?): AgentErrorEnvelope? {
        if (body == null) return null
        return runCatching { adapter.fromJson(body.string()) }.getOrNull()
    }

    fun parse(response: Response<*>): AgentErrorEnvelope? {
        return parse(response.errorBody())
    }

    fun isApprovalRequired(error: AgentErrorEnvelope?): Boolean =
        error?.errorCode() == AgentErrorCode.AGENT_APPROVAL_REQUIRED

    fun isAcademicRestricted(error: AgentErrorEnvelope?): Boolean =
        error?.errorCode() == AgentErrorCode.AGENT_ACADEMIC_POLICY_RESTRICTED

    fun isIdempotencyConflict(error: AgentErrorEnvelope?): Boolean =
        error?.errorCode() == AgentErrorCode.AGENT_IDEMPOTENCY_CONFLICT
}