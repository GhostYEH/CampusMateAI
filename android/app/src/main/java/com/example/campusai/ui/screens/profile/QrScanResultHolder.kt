package com.example.campusai.ui.screens.profile

/**
 * 临时持有扫码结果，供 QrConfirmScreen 读取。
 * 避免将 scanToken 等参数通过 URL 路径传递。
 */
object QrScanResultHolder {
    var sessionId: String? = null
    var scanToken: String? = null
    var browserName: String? = null
    var osName: String? = null
    var deviceLabel: String? = null

    fun set(sid: String, token: String, bName: String?, oName: String?, dLabel: String?) {
        sessionId = sid
        scanToken = token
        browserName = bName
        osName = oName
        deviceLabel = dLabel
    }

    fun clear() {
        sessionId = null
        scanToken = null
        browserName = null
        osName = null
        deviceLabel = null
    }
}