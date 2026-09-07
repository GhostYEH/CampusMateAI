const weekdayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export function deadlineLabel(value, now) {
  if (!value) return "未设置截止";
  const date = new Date(value);
  if (Number.isNaN(date.valueOf())) return "截止时间待确认";
  const current = new Date(now);
  if (date.toDateString() === current.toDateString()) {
    return `今日截止 ${date.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  }
  return date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function sectionLabel(item) {
  const start = item?.start_section;
  const end = item?.end_section ?? start;
  if (!start) return "时间待定";
  return start === end ? `第 ${start} 节` : `第 ${start}-${end} 节`;
}

export function scheduleWeekOf(now = new Date()) {
  const current = new Date(now);
  if (Number.isNaN(current.valueOf())) return { label: "", days: [] };
  const mondayOffset = (current.getDay() + 6) % 7;
  const start = new Date(current);
  start.setDate(current.getDate() - mondayOffset);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  const todayIndex = current.getDay() || 7;
  const dateText = (value) => `${value.getMonth() + 1}月${value.getDate()}日`;
  return {
    label: `${dateText(start)} – ${dateText(end)}`,
    days: Array.from({ length: 7 }, (_, index) => {
      const date = new Date(start);
      date.setDate(start.getDate() + index);
      return { name: weekdayNames[index].replace("周", ""), date: date.getDate(), isToday: index + 1 === todayIndex };
    }),
  };
}
