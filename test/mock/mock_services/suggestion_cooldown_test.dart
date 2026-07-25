import 'package:flutter_test/flutter_test.dart';
import 'package:campus_companion/mock/mock_services/expression_smoother.dart';

void main() {
  group('SuggestionCooldown', () {
    test('未触发过时 canTrigger 为 true', () {
      final c = SuggestionCooldown(cooldownMinutes: 15);
      expect(c.canTrigger(now: DateTime(2025, 1, 1, 10, 0)), isTrue);
    });

    test('冷却期内 canTrigger 为 false', () {
      final c = SuggestionCooldown(cooldownMinutes: 15);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      c.markTriggered(now: t0);

      // 10 分钟后,仍在 15 分钟冷却内
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 10))), isFalse);
      // 14 分 59 秒后,仍在冷却内
      expect(
        c.canTrigger(now: t0.add(const Duration(seconds: 14 * 60 + 59))),
        isFalse,
      );
    });

    test('冷却结束后 canTrigger 为 true', () {
      final c = SuggestionCooldown(cooldownMinutes: 15);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      c.markTriggered(now: t0);

      // 15 分钟整,冷却结束
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 15))), isTrue);
      // 20 分钟后,肯定结束
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 20))), isTrue);
    });

    test('多次触发: 每次都以最近触发时间计算冷却', () {
      final c = SuggestionCooldown(cooldownMinutes: 10);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      c.markTriggered(now: t0);

      // 8 分钟后仍在冷却
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 8))), isFalse);

      // 在 8 分钟时再次触发,冷却应从 8 分钟处开始算 10 分钟
      c.markTriggered(now: t0.add(const Duration(minutes: 8)));

      // 距离第一次 12 分钟,如果没有重新触发应该已结束(>=10)
      // 但因为 8 分钟时重新触发了,所以距新触发只过了 4 分钟,应仍在冷却
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 12))), isFalse);

      // 距新触发 10 分钟(总 18 分钟),冷却结束
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 18))), isTrue);
    });

    test('remainingSeconds 返回剩余冷却秒数', () {
      final c = SuggestionCooldown(cooldownMinutes: 10);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      // 未触发过,剩余 0
      expect(c.remainingSeconds(now: t0), 0);

      c.markTriggered(now: t0);
      // 触发后立即查询,剩余 = 10*60 = 600 秒
      expect(c.remainingSeconds(now: t0), 600);

      // 3 分钟后,剩余 7*60 = 420 秒
      expect(c.remainingSeconds(now: t0.add(const Duration(minutes: 3))), 420);

      // 10 分钟后,剩余 0
      expect(c.remainingSeconds(now: t0.add(const Duration(minutes: 10))), 0);

      // 15 分钟后,剩余仍为 0(不会变负)
      expect(c.remainingSeconds(now: t0.add(const Duration(minutes: 15))), 0);
    });

    test('reset 清除触发记录', () {
      final c = SuggestionCooldown(cooldownMinutes: 30);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      c.markTriggered(now: t0);
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 5))), isFalse);

      c.reset();
      expect(c.canTrigger(now: t0.add(const Duration(minutes: 5))), isTrue);
      expect(c.remainingSeconds(now: t0), 0);
    });

    test('cooldownMinutes=0 时永远可触发', () {
      final c = SuggestionCooldown(cooldownMinutes: 0);
      final t0 = DateTime(2025, 1, 1, 10, 0);
      c.markTriggered(now: t0);
      // 立即可触发(0 分钟冷却)
      expect(c.canTrigger(now: t0), isTrue);
      expect(c.remainingSeconds(now: t0), 0);
    });
  });
}
