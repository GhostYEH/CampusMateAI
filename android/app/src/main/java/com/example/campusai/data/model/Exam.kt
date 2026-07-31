package com.example.campusai.data.model

import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** 考试状态：仅区分未开始 / 已结束，与筛选 Tab 对应。 */
enum class ExamStatus { UPCOMING, ENDED }

/**
 * 考试安排。日期与时间使用 ISO 字符串(yyyy-MM-dd / HH:mm)存储，
 * 便于 Moshi 序列化与本地持久化。
 */
data class Exam(
    val id: Long,
    val courseName: String,
    val date: String,
    val startTime: String,
    val endTime: String,
    val location: String,
    val seatNumber: String,
    val type: String,
    val reminderEnabled: Boolean = true,
) {
    fun startDateTime(): LocalDateTime? = runCatching {
        LocalDateTime.of(LocalDate.parse(date), LocalTime.parse(startTime))
    }.getOrNull()

    fun endDateTime(): LocalDateTime? = runCatching {
        LocalDateTime.of(LocalDate.parse(date), LocalTime.parse(endTime))
    }.getOrNull()

    fun statusAt(nowMillis: Long, zone: ZoneId = ZoneId.systemDefault()): ExamStatus {
        val end = endDateTime() ?: return ExamStatus.ENDED
        val endMillis = end.atZone(zone).toInstant().toEpochMilli()
        return if (nowMillis < endMillis) ExamStatus.UPCOMING else ExamStatus.ENDED
    }

    /** 距离考试开始的整天数；未开始返回 >= 0，否则返回 null。 */
    fun daysUntil(nowMillis: Long, zone: ZoneId = ZoneId.systemDefault()): Long? {
        val start = startDateTime() ?: return null
        val startMillis = start.atZone(zone).toInstant().toEpochMilli()
        if (nowMillis >= startMillis) return null
        return (startMillis - nowMillis) / (24 * 60 * 60 * 1000) + 1
    }

    fun dateLabel(): String = runCatching {
        LocalDate.parse(date).format(DATE_LABEL_FORMAT)
    }.getOrDefault(date)

    companion object {
        private val DATE_LABEL_FORMAT: DateTimeFormatter = DateTimeFormatter.ofPattern("M月d日 EEEE")
    }
}
