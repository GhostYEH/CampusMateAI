export function groupScheduleByWeekday(items) {
  const grouped = Array.from({ length: 7 }, () => []);

  (items || []).forEach((item) => {
    const weekday = Number(item.weekday);
    if (item.is_stale || !Number.isInteger(weekday) || weekday < 1 || weekday > 7) return;
    grouped[weekday - 1].push(item);
  });

  grouped.forEach((dayItems) => {
    dayItems.sort((left, right) => Number(left.start_section || 0) - Number(right.start_section || 0));
  });
  return grouped;
}