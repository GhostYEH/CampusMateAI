package com.example.campusai.data.repository

import com.example.campusai.data.model.Course
import com.example.campusai.data.model.Task
import com.example.campusai.data.remote.CourseContentItemDto
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

private val campusZone = ZoneId.of("Asia/Shanghai")

internal fun String.courseDateInstant(): Instant? = runCatching { Instant.parse(this) }.getOrNull()
    ?: runCatching { OffsetDateTime.parse(this).toInstant() }.getOrNull()
    ?: runCatching { LocalDateTime.parse(this.replace(' ', 'T')).atZone(campusZone).toInstant() }.getOrNull()
    ?: runCatching { LocalDateTime.parse(this.replace('T', ' '),
        DateTimeFormatter.ofPattern("yyyy-M-d H:mm")).atZone(campusZone).toInstant() }.getOrNull()
    ?: runCatching { LocalDate.parse(this.take(10),
        DateTimeFormatter.ofPattern("yyyy-M-d")).atStartOfDay(campusZone).toInstant() }.getOrNull()

internal fun String.courseDeadlineInstant(): Instant? {
    val normalized = replace('/', '-')
    if (Regex("^\\d{4}-\\d{1,2}-\\d{1,2}$").matches(normalized)) {
        val date = runCatching { LocalDate.parse(normalized, DateTimeFormatter.ofPattern("yyyy-M-d")) }.getOrNull()
        return date?.plusDays(1)?.atStartOfDay(campusZone)?.toInstant()
    }
    return normalized.courseDateInstant()
}

internal fun Course.isCurrentSemesterAt(now: Instant): Boolean {
    val date = now.atZone(campusZone).toLocalDate()
    val semesterStart = when {
        date.monthValue >= 8 -> LocalDate.of(date.year, 8, 1)
        date.monthValue == 1 -> LocalDate.of(date.year - 1, 8, 1)
        else -> LocalDate.of(date.year, 2, 1)
    }.atStartOfDay(campusZone).toInstant()
    val start = startsAt?.courseDateInstant() ?: return false
    val end = endsAt?.courseDeadlineInstant() ?: return false
    return !start.isBefore(semesterStart) && !start.isAfter(now) && end.isAfter(now)
}

/** Only explicit assignment notices with both dates can become a provisional task. */
internal fun assignmentFromNotice(course: Course, notice: CourseContentItemDto): Task? {
    if (notice.kind != "notice") return null
    val content = listOf(notice.title, notice.description.orEmpty()).joinToString("\n")
    if (!content.contains("作业") && !content.contains("实验")) return null
    val date = "([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}(?:[ T][0-9]{1,2}:[0-9]{2})?)"
    val start = Regex("(?:开始时间|开放时间)[：:\\s]*$date").find(content)?.groupValues?.get(1)
        ?: return null
    val deadline = Regex("(?:结束时间|截止时间|截止日期)[：:\\s]*$date").find(content)?.groupValues?.get(1)
        ?: return null
    val assignmentName = Regex("作业名称[：:]([^\\r\\n]+)").find(content)?.groupValues?.get(1)?.trim()
        ?: notice.title
    return Task(
        id = "course-notice:${course.id}:${notice.external_id.ifBlank { notice.id }}",
        title = assignmentName,
        due = deadline.replace('/', '-'),
        course = course.name,
        done = false,
        description = content,
        source = "course_notice",
        courseId = course.id,
        startAt = start.replace('/', '-'),
        externalId = notice.external_id,
    )
}
