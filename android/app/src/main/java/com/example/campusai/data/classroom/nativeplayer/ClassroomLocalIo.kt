package com.example.campusai.data.classroom.nativeplayer

import com.example.campusai.data.repository.AppRepository

/**
 * 原生课堂位置与奖励账本的本地读写入口。
 *
 * 生产实现按「账号 + 课堂键」读写 DataStore；测试可用可挂起的替身安排写入、
 * 回读与取消的先后顺序。所有写入都带最终代次守卫，返回是否真正落盘。
 */
internal interface ClassroomLocalIo {
    suspend fun readPosition(accountScope: String): String?

    suspend fun readRewardsRaw(accountScope: String): String?

    suspend fun savePosition(
        sceneId: String,
        accountScope: String,
        shouldWrite: () -> Boolean,
    ): Boolean

    suspend fun saveRewardsRaw(
        raw: String,
        accountScope: String,
        shouldWrite: () -> Boolean,
    ): Boolean
}

internal class RepositoryClassroomLocalIo(
    private val repository: AppRepository,
    private val ref: NativeClassroomRef,
) : ClassroomLocalIo {
    override suspend fun readPosition(accountScope: String): String? =
        repository.classroomPosition(ref, accountScope)

    override suspend fun readRewardsRaw(accountScope: String): String? =
        repository.classroomRewardsRaw(ref, accountScope)

    override suspend fun savePosition(
        sceneId: String,
        accountScope: String,
        shouldWrite: () -> Boolean,
    ): Boolean = repository.saveClassroomPosition(ref, sceneId, accountScope, shouldWrite)

    override suspend fun saveRewardsRaw(
        raw: String,
        accountScope: String,
        shouldWrite: () -> Boolean,
    ): Boolean = repository.saveClassroomRewardsRaw(ref, raw, accountScope, shouldWrite)
}
