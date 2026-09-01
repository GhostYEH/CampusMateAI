package com.example.campusai.features.gamification

import com.example.campusai.data.local.KeyValueStorage
import com.squareup.moshi.FromJson
import com.squareup.moshi.Moshi
import com.squareup.moshi.ToJson
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import java.time.Instant
import java.time.ZoneId
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class GamificationSnapshotCodec {
    private class InstantAdapter {
        @ToJson fun toJson(value: Instant): String = value.toString()
        @FromJson fun fromJson(value: String): Instant = Instant.parse(value)
    }

    private val adapter = Moshi.Builder()
        .add(InstantAdapter())
        .addLast(KotlinJsonAdapterFactory())
        .build()
        .adapter(GamificationSnapshot::class.java)

    fun encode(snapshot: GamificationSnapshot): String = adapter.toJson(snapshot)

    fun decode(raw: String): GamificationSnapshot? = runCatching {
        adapter.fromJson(raw)?.takeIf { it.version == GamificationSnapshot.CURRENT_VERSION }
    }.getOrNull()
}

class GamificationStore(
    private val storage: KeyValueStorage,
    private val codec: GamificationSnapshotCodec = GamificationSnapshotCodec(),
) {
    private val mutex = Mutex()
    private val _snapshot = MutableStateFlow(GamificationSnapshot())
    val snapshot: StateFlow<GamificationSnapshot> = _snapshot.asStateFlow()

    private var storageKey: String? = null

    suspend fun activate(accountKey: String?) = mutex.withLock {
        storageKey = accountKey?.takeIf(String::isNotBlank)?.let { "gamification_snapshot_$it" }
        _snapshot.value = storageKey
            ?.let { key -> storage.readRaw(key)?.let(codec::decode) }
            ?: GamificationSnapshot()
    }

    suspend fun reconcile(
        facts: GamificationFacts,
        now: Instant = Instant.now(),
        zoneId: ZoneId = ZoneId.systemDefault(),
    ): GamificationSnapshot = mutex.withLock {
        val key = storageKey ?: return@withLock _snapshot.value
        val updated = GamificationEngine.reconcile(_snapshot.value, facts, now, zoneId)
        if (updated != _snapshot.value) {
            storage.saveRaw(key, codec.encode(updated))
            _snapshot.value = updated
        }
        updated
    }
}
