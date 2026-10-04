package com.example.campusai.data.repository

import com.example.campusai.data.remote.ChaoxingSyncStatusResponse
import org.json.JSONObject
import retrofit2.Response

private fun credentialsUnavailable(errorBody: String): Boolean = runCatching {
    JSONObject(errorBody).optString("code") == "CHAOXING_CREDENTIALS_UNAVAILABLE"
}.getOrDefault(false)

internal fun chaoxingSyncFailure(httpStatus: Int, errorBody: String): String = when {
    httpStatus == 403 || errorBody.contains("verification_required") -> "verification_required"
    credentialsUnavailable(errorBody) || httpStatus == 401 || errorBody.contains("reauth_required") -> "reauth_required"
    else -> "同步失败: $httpStatus"
}

internal fun chaoxingStatus(response: Response<ChaoxingSyncStatusResponse>): ChaoxingSyncStatusResponse? {
    if (response.isSuccessful) return response.body()
    // Use the existing reconnect form. Transient HTTP failures remain unknown
    // and must not clear the previously confirmed connection.
    return if (credentialsUnavailable(response.errorBody()?.string().orEmpty())) {
        ChaoxingSyncStatusResponse(status = "expired", last_synced_at = null)
    } else null
}
