import 'package:intl/intl.dart';

/// 日期与时间工具。
class AppDateUtils {
  AppDateUtils._();

  /// 根据当前时间返回问候语。
  static String greeting(DateTime now) {
    final hour = now.hour;
    if (hour >= 5 && hour < 11) return '早上好';
    if (hour >= 11 && hour < 13) return '中午好';
    if (hour >= 13 && hour < 18) return '下午好';
    if (hour >= 18 && hour < 23) return '晚上好';
    return '夜深了';
  }

  /// 中文星期。
  static const _weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

  static String weekday(DateTime date) {
    // DateTime.weekday: Monday=1..Sunday=7
    return _weekdays[date.weekday - 1];
  }

  /// 完整日期: "10月20日 周三"
  static String formatDate(DateTime date) {
    return '${date.month}月${date.day}日 ${weekday(date)}';
  }

  /// 带年份: "2024年10月20日 周三"
  static String formatDateFull(DateTime date) {
    return '${date.year}年${date.month}月${date.day}日 ${weekday(date)}';
  }

  /// 时间: "14:30"
  static String formatTime(DateTime date) {
    return DateFormat('HH:mm').format(date);
  }

  /// 相对时间: "刚刚 / 5分钟前 / 2小时前 / 昨天 / 10月20日"
  static String relativeTime(DateTime date, {DateTime? now}) {
    final reference = now ?? DateTime.now();
    final diff = reference.difference(date);
    if (diff.inMinutes < 1) return '刚刚';
    if (diff.inMinutes < 60) return '${diff.inMinutes}分钟前';
    if (diff.inHours < 24 && reference.day == date.day) {
      return '${diff.inHours}小时前';
    }
    if (diff.inDays == 0 && reference.day - date.day == 1) {
      return '昨天 ${formatTime(date)}';
    }
    if (diff.inDays < 7) return '${diff.inDays}天前';
    return DateFormat('MM月dd日').format(date);
  }

  /// 截止倒计时描述。
  /// 返回 (文本, 紧急等级 0=正常 1=临近 2=紧急 3=逾期)。
  static ({String text, DeadlineUrgency urgency}) deadlineCountdown(
    DateTime? deadline, {
    DateTime? now,
  }) {
    if (deadline == null) {
      return (text: '未设置截止', urgency: DeadlineUrgency.none);
    }
    final reference = now ?? DateTime.now();
    final remaining = deadline.difference(reference);

    if (remaining.isNegative) {
      final overdueDays = -remaining.inDays;
      final overdueHours = (-remaining.inHours);
      if (overdueDays >= 1) {
        return (text: '已逾期 $overdueDays 天', urgency: DeadlineUrgency.overdue);
      }
      return (text: '已逾期 $overdueHours 小时', urgency: DeadlineUrgency.overdue);
    }
    if (remaining.inDays >= 7) {
      return (text: '剩 ${remaining.inDays} 天', urgency: DeadlineUrgency.normal);
    }
    if (remaining.inDays >= 3) {
      return (text: '剩 ${remaining.inDays} 天', urgency: DeadlineUrgency.soon);
    }
    if (remaining.inDays >= 1) {
      return (text: '剩 ${remaining.inDays} 天', urgency: DeadlineUrgency.urgent);
    }
    if (remaining.inHours >= 1) {
      return (
        text: '剩 ${remaining.inHours} 小时',
        urgency: DeadlineUrgency.urgent
      );
    }
    return (
      text: '剩 ${remaining.inMinutes} 分钟',
      urgency: DeadlineUrgency.urgent
    );
  }

  /// 是否今天。
  static bool isSameDay(DateTime a, DateTime b) {
    return a.year == b.year && a.month == b.month && a.day == b.day;
  }

  /// 是否今天。
  static bool isToday(DateTime date) => isSameDay(date, DateTime.now());

  /// 是否本周。
  static bool isThisWeek(DateTime date) {
    final now = DateTime.now();
    final start = now.subtract(Duration(days: now.weekday - 1));
    final s = DateTime(start.year, start.month, start.day);
    return date.isAfter(s.subtract(const Duration(seconds: 1))) &&
        date.isBefore(s.add(const Duration(days: 7)));
  }

  /// 计算年龄(分钟)。
  static int ageInMinutes(DateTime date) {
    return DateTime.now().difference(date).inMinutes;
  }
}

/// 截止紧急等级。
enum DeadlineUrgency {
  none, // 未设置
  normal, // 正常 (>7天)
  soon, // 临近 (3-7天)
  urgent, // 紧急 (<3天 / 逾期)
  overdue, // 已逾期
}
