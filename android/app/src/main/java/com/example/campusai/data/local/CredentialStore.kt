package com.example.campusai.data.local

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/**
 * 使用 Jetpack Security 的 EncryptedSharedPreferences（基于 Android Keystore，AES256）
 * 加密保存「记住的账号密码」。Keystore 不可用时降级为不保存，绝不明文落盘。
 */
class CredentialStore(private val context: Context) {

    data class SavedCredential(val username: String, val password: String)

    private val prefs: SharedPreferences? by lazy {
        try {
            val masterKey = MasterKey.Builder(context)
                .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                .build()
            EncryptedSharedPreferences.create(
                context,
                "campus_credentials",
                masterKey,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        } catch (_: Exception) {
            null
        }
    }

    suspend fun save(username: String, password: String) = withContext(Dispatchers.IO) {
        try {
            prefs?.edit()?.apply {
                putString(KEY_USERNAME, username)
                putString(KEY_PASSWORD, password)
                apply()
            }
        } catch (_: Exception) { }
    }

    suspend fun load(): SavedCredential? = withContext(Dispatchers.IO) {
        try {
            val u = prefs?.getString(KEY_USERNAME, null)
            val p = prefs?.getString(KEY_PASSWORD, null)
            if (!u.isNullOrEmpty() && !p.isNullOrEmpty()) SavedCredential(u, p) else null
        } catch (_: Exception) { null }
    }

    suspend fun savedUsername(): String? = withContext(Dispatchers.IO) {
        try { prefs?.getString(KEY_USERNAME, null) } catch (_: Exception) { null }
    }

    suspend fun clear() = withContext(Dispatchers.IO) {
        try { prefs?.edit()?.clear()?.apply() } catch (_: Exception) { }
    }

    companion object {
        private const val KEY_USERNAME = "username"
        private const val KEY_PASSWORD = "password"
    }
}