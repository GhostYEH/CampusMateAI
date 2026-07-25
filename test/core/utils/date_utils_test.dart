import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/core/utils/date_utils.dart';

void main() {
  group('AppDateUtils.greeting', () {
    test('根据小时返回对应问候语', () {
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 6)), '早上好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 10)), '早上好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 11)), '中午好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 12)), '中午好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 13)), '下午好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 17)), '下午好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 18)), '晚上好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 22)), '晚上好');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 23)), '夜深了');
      expect(AppDateUtils.greeting(DateTime(2025, 10, 1, 2)), '夜深了');
    });
  });

  group('AppDateUtils.weekday', () {
    test('周一至周日映射正确', () {
      expect(
        AppDateUtils.weekday(DateTime(2025, 10, 13)),
        '周一',
      ); // 2025-10-13 是周一
      expect(AppDateUtils.weekday(DateTime(2025, 10, 14)), '周二');
      expect(AppDateUtils.weekday(DateTime(2025, 10, 15)), '周三');
      expect(AppDateUtils.weekday(DateTime(2025, 10, 16)), '周四');
      expect(AppDateUtils.weekday(DateTime(2025, 10, 17)), '周五');
      expect(AppDateUtils.weekday(DateTime(2025, 10, 18)), '周六');
      expect(AppDateUtils.weekday(DateTime(2025, 10, 19)), '周日');
    });
  });

  group('AppDateUtils.formatDate / formatDateFull', () {
    test('formatDate 不含年份', () {
      expect(
        AppDateUtils.formatDate(DateTime(2025, 10, 20)),
        contains('10月20日'),
      );
      expect(AppDateUtils.formatDate(DateTime(2025, 10, 20)), contains('周'));
    });

    test('formatDateFull 含年份', () {
      final s = AppDateUtils.formatDateFull(DateTime(2025, 10, 20));
      expect(s, contains('2025年'));
      expect(s, contains('10月20日'));
    });
  });

  group('AppDateUtils.formatTime', () {
    test('24小时制时分', () {
      expect(AppDateUtils.formatTime(DateTime(2025, 10, 1, 9, 5)), '09:05');
      expect(AppDateUtils.formatTime(DateTime(2025, 10, 1, 14, 30)), '14:30');
      expect(AppDateUtils.formatTime(DateTime(2025, 10, 1, 0, 0)), '00:00');
    });
  });

  group('AppDateUtils.relativeTime', () {
    final now = DateTime(2025, 10, 15, 12, 0);

    test('刚刚(不足1分钟)', () {
      expect(
        AppDateUtils.relativeTime(
          now.subtract(const Duration(seconds: 30)),
          now: now,
        ),
        '刚刚',
      );
    });

    test('N分钟前', () {
      expect(
        AppDateUtils.relativeTime(
          now.subtract(const Duration(minutes: 5)),
          now: now,
        ),
        '5分钟前',
      );
    });

    test('N小时前(同一天)', () {
      expect(
        AppDateUtils.relativeTime(
          now.subtract(const Duration(hours: 3)),
          now: now,
        ),
        '3小时前',
      );
    });

    test('N天前(7天内)', () {
      expect(
        AppDateUtils.relativeTime(
          now.subtract(const Duration(days: 2)),
          now: now,
        ),
        '2天前',
      );
    });

    test('7天以上显示月日', () {
      final old = DateTime(2025, 9, 1, 12, 0);
      final s = AppDateUtils.relativeTime(old, now: now);
      expect(s, contains('09月'));
      expect(s, contains('01日'));
    });
  });

  group('AppDateUtils.deadlineCountdown - 截止倒计时', () {
    final now = DateTime(2025, 10, 15, 12, 0);

    test('未设置截止返回 none 紧急等级', () {
      final r = AppDateUtils.deadlineCountdown(null, now: now);
      expect(r.urgency, DeadlineUrgency.none);
      expect(r.text, '未设置截止');
    });

    test('已逾期: 超过1天显示逾期天数', () {
      final r = AppDateUtils.deadlineCountdown(
        now.subtract(const Duration(days: 3)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.overdue);
      expect(r.text, contains('已逾期'));
      expect(r.text, contains('3'));
      expect(r.text, contains('天'));
    });

    test('已逾期: 不足1天显示小时', () {
      final r = AppDateUtils.deadlineCountdown(
        now.subtract(const Duration(hours: 5)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.overdue);
      expect(r.text, contains('小时'));
    });

    test('剩 >=7 天: normal', () {
      final r = AppDateUtils.deadlineCountdown(
        now.add(const Duration(days: 10)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.normal);
      expect(r.text, contains('10'));
      expect(r.text, contains('天'));
    });

    test('剩 3-7 天: soon', () {
      final r = AppDateUtils.deadlineCountdown(
        now.add(const Duration(days: 5)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.soon);
    });

    test('剩 1-3 天: urgent', () {
      final r = AppDateUtils.deadlineCountdown(
        now.add(const Duration(days: 2)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.urgent);
    });

    test('剩 1-24 小时: urgent + 小时', () {
      final r = AppDateUtils.deadlineCountdown(
        now.add(const Duration(hours: 5)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.urgent);
      expect(r.text, contains('5 小时'));
    });

    test('剩 <1 小时: urgent + 分钟', () {
      final r = AppDateUtils.deadlineCountdown(
        now.add(const Duration(minutes: 30)),
        now: now,
      );
      expect(r.urgency, DeadlineUrgency.urgent);
      expect(r.text, contains('分钟'));
    });
  });

  group('AppDateUtils.isSameDay / isToday / isThisWeek', () {
    test('isSameDay 仅比较年月日', () {
      final a = DateTime(2025, 10, 15, 8, 0);
      final b = DateTime(2025, 10, 15, 23, 59);
      expect(AppDateUtils.isSameDay(a, b), isTrue);
      expect(AppDateUtils.isSameDay(a, DateTime(2025, 10, 16)), isFalse);
    });

    test('isThisWeek 本周内为 true,本周外为 false', () {
      final now = DateTime.now();
      // 本周周一
      final monday = now.subtract(Duration(days: now.weekday - 1));
      final mondayStart = DateTime(monday.year, monday.month, monday.day);
      // 本周周日 23:59
      final sundayEnd = mondayStart
          .add(const Duration(days: 7))
          .subtract(const Duration(seconds: 1));

      expect(
        AppDateUtils.isThisWeek(mondayStart.add(const Duration(hours: 12))),
        isTrue,
      );
      expect(AppDateUtils.isThisWeek(sundayEnd), isTrue);
      // 上周一应该不在本周
      final lastWeek = mondayStart.subtract(const Duration(days: 7));
      expect(AppDateUtils.isThisWeek(lastWeek), isFalse);
    });
  });
}
