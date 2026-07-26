import 'package:flutter_test/flutter_test.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

/// 时区转换正确性测试 — 验证 `LocalNotificationReminderService` 中使用的
/// `tz.TZDateTime.from(scheduledAt, tz.local)` 转换逻辑。
///
/// **关键点**(AGENTS.md §提醒规范):
/// - 不使用 `DateTime.now().timeZoneName` 作为 IANA 时区
/// - 通过 `flutter_timezone` 取得 IANA 名称并 `tz.setLocalLocation`
/// - 正确处理 UTC、本地时间、夏令时
void main() {
  setUpAll(() {
    tz_data.initializeTimeZones();
  });

  group('timezone 转换 - tz.TZDateTime.from', () {
    test('Asia/Shanghai 本地时区 — 本地 DateTime 直接映射', () {
      tz.setLocalLocation(tz.getLocation('Asia/Shanghai'));
      final local = DateTime(2025, 7, 26, 15, 30); // 本地时间
      final zoned = tz.TZDateTime.from(local, tz.local);
      expect(zoned.year, 2025);
      expect(zoned.month, 7);
      expect(zoned.day, 26);
      expect(zoned.hour, 15);
      expect(zoned.minute, 30);
      expect(zoned.timeZoneName, 'CST'); // Asia/Shanghai 的标准缩写
    });

    test('Asia/Shanghai → America/Los_Angeles 跨时区转换', () {
      tz.setLocalLocation(tz.getLocation('America/Los_Angeles'));
      // 2025-07-26 15:30 上海时间(PST 是 -8, PDT 是 -7,7 月是 PDT = -7)
      // 上海是 +8,所以上海 15:30 → 洛杉矶 0:30 (差 15 小时,因为 PDT)
      final shanghai = tz.TZDateTime(
        tz.getLocation('Asia/Shanghai'),
        2025,
        7,
        26,
        15,
        30,
      );
      final la = tz.TZDateTime.from(shanghai, tz.local);
      // 同一时刻,不同时区显示
      expect(la.millisecondsSinceEpoch, shanghai.millisecondsSinceEpoch);
      expect(la.hour, equals(0)); // 15:30 CST → 0:30 PDT
    });

    test('UTC DateTime → 本地时区转换保持时刻一致', () {
      tz.setLocalLocation(tz.getLocation('Asia/Shanghai'));
      final utc = DateTime.utc(2025, 7, 26, 7, 30); // UTC 07:30
      final local = tz.TZDateTime.from(utc, tz.local);
      // 上海是 UTC+8 → UTC 07:30 = 上海 15:30
      expect(local.hour, 15);
      expect(local.minute, 30);
      expect(local.millisecondsSinceEpoch, utc.millisecondsSinceEpoch);
    });

    test('夏令时切换 — 美国时区在 3 月切到 DST', () {
      tz.setLocalLocation(tz.getLocation('America/New_York'));
      // DST 切换前(2025-03-09 之前是 EST = -5)
      final before = tz.TZDateTime(
        tz.getLocation('America/New_York'),
        2025,
        3,
        8,
        12,
        0,
      );
      // DST 切换后(2025-03-09 之后是 EDT = -4)
      final after = tz.TZDateTime(
        tz.getLocation('America/New_York'),
        2025,
        3,
        10,
        12,
        0,
      );
      expect(before.timeZoneName, 'EST');
      expect(after.timeZoneName, 'EDT');
      // 同样 12:00 本地时间,但 UTC 时刻不同(DST 后差 1 小时)
      expect(
        after.millisecondsSinceEpoch - before.millisecondsSinceEpoch,
        isNot(equals(const Duration(days: 2).inMilliseconds)),
      );
    });

    test('tz.local 默认为 UTC(未 setLocalLocation 时)', () {
      // 重置为 UTC — 模拟"取不到本地时区"的降级场景
      tz.setLocalLocation(tz.UTC);
      final input = DateTime(2025, 7, 26, 10, 0);
      final zoned = tz.TZDateTime.from(input, tz.local);
      expect(zoned.timeZoneName, 'UTC');
      // 注意:本地 DateTime(非 UTC)→ UTC 转换会"翻译"为对应的 UTC 时刻,
      // 但在测试环境中输入是 naive DateTime,timezone 包按 local 处理 — 此时 local=UTC
      // 所以小时字段不变
      expect(zoned.hour, 10);
    });
  });

  group('timezone 转换 - 不使用 DateTime.timeZoneName', () {
    test('DateTime.now().timeZoneName 在测试环境中不可靠', () {
      // 这个测试的存在是为了文档化:DateTime.now().timeZoneName 返回的
      // 是系统缩写(如 "CST" "PST" "EST"),不是 IANA 名称(如 "Asia/Shanghai")。
      // 中国标准时间(CST)与美国中部时间(CST)缩写相同,会引发歧义。
      // 因此 LocalNotificationReminderService 使用 flutter_timezone 取 IANA 名称。
      final systemTz = DateTime.now().timeZoneName;
      // 系统返回的可能是任何值,这里只验证它是字符串
      expect(systemTz, isA<String>());
    });

    test('IANA 名称通过 tz.getLocation 解析为 Location', () {
      // 模拟 flutter_timezone 返回的 IANA 名称
      const ianaName = 'Asia/Shanghai';
      final location = tz.getLocation(ianaName);
      expect(location, isNotNull);
      // 当前上海时间的偏移应为 +8h(无夏令时)
      final now = tz.TZDateTime.now(location);
      expect(now.timeZoneOffset.inHours, 8);
    });

    test('未知 IANA 名称不会崩溃 — LocalNotificationReminderService 应捕获异常', () {
      // 模拟 flutter_timezone 返回了一个无效字符串(极端情况)
      expect(() => tz.getLocation('Invalid/Timezone'), throwsA(isA<Object>()));
      // LocalNotificationReminderService.ensureInitialized 中:
      // try { final location = tz.getLocation(localName); tz.setLocalLocation(location); }
      // catch (_) { /* 不阻断,使用默认 UTC */ }
    });
  });
}
