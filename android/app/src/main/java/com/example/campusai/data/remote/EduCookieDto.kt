package com.example.campusai.data.remote

/** Scoped cookie contract; unavailable WebView attributes stay null. */
data class EduCookieDto(
    val name: String,
    val value: String,
    val domain: String? = null,
    val source_url: String? = null,
    val host_only: Boolean? = null,
    val path: String? = null,
    val secure: Boolean? = null,
    val http_only: Boolean? = null,
    val same_site: String? = null,
    val expires: Long? = null,
)
