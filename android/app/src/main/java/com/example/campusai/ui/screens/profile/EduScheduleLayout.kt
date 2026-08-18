package com.example.campusai.ui.screens.profile

import com.example.campusai.data.remote.EduScheduleItemDto

data class SchedulePlacement(
    val item: EduScheduleItemDto,
    val startSection: Int,
    val endSection: Int,
    val lane: Int,
    val laneCount: Int,
) {
    val durationSections: Int get() = endSection - startSection + 1
}

data class ScheduleLayout(
    val maxSection: Int,
    val placements: List<SchedulePlacement>,
)

private data class ValidItem(
    val sourceIndex: Int,
    val item: EduScheduleItemDto,
    val weekday: Int,
    val start: Int,
    val end: Int,
)

fun layoutScheduleItems(
    items: List<EduScheduleItemDto>,
    minimumSections: Int = 12,
): ScheduleLayout {
    val valid = items.mapIndexedNotNull { index, item ->
        val weekday = item.weekday?.takeIf { it in 1..7 } ?: return@mapIndexedNotNull null
        val start = item.start_section?.takeIf { it >= 1 } ?: return@mapIndexedNotNull null
        val end = (item.end_section ?: start).takeIf { it >= start } ?: return@mapIndexedNotNull null
        ValidItem(index, item, weekday, start, end)
    }
    val maxSection = maxOf(minimumSections.coerceAtLeast(1), valid.maxOfOrNull { it.end } ?: 0)
    val placements = mutableListOf<SchedulePlacement>()

    valid.groupBy { it.weekday }.toSortedMap().values.forEach { dayItems ->
        val sorted = dayItems.sortedWith(compareBy<ValidItem> { it.start }.thenBy { it.end }.thenBy { it.sourceIndex })
        val lanes = mutableListOf<MutableList<ValidItem>>()
        val laneByIndex = mutableMapOf<Int, Int>()
        sorted.forEach { current ->
            val lane = lanes.indexOfFirst { existing ->
                existing.none { it.start <= current.end && current.start <= it.end }
            }.let { if (it >= 0) it else lanes.size }
            if (lane == lanes.size) lanes.add(mutableListOf())
            lanes[lane].add(current)
            laneByIndex[current.sourceIndex] = lane
        }

        val components = mutableListOf<MutableList<ValidItem>>()
        sorted.forEach { current ->
            val component = components.firstOrNull { component ->
                component.any { it.start <= current.end && current.start <= it.end }
            }
            if (component == null) components.add(mutableListOf(current)) else component.add(current)
        }
        components.forEach { component ->
            val componentLaneCount = component.maxOf { (laneByIndex[it.sourceIndex] ?: 0) + 1 }
            component.forEach { current ->
                placements.add(
                    SchedulePlacement(
                        item = current.item,
                        startSection = current.start,
                        endSection = current.end,
                        lane = laneByIndex[current.sourceIndex] ?: 0,
                        laneCount = componentLaneCount,
                    )
                )
            }
        }
    }
    return ScheduleLayout(maxSection = maxSection, placements = placements.sortedWith(compareBy({ it.item.weekday ?: 99 }, { it.startSection }, { it.lane })))
}
