import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:campus_companion/core/storage/local_storage.dart';

void main() {
  group('JsonCodecHelper', () {
    test('encode / decode Map 往返一致', () {
      final json = {'a': 1, 'b': 'string', 'c': true, 'd': null};
      final encoded = JsonCodecHelper.encode(json);
      final decoded = JsonCodecHelper.decode(encoded);
      expect(decoded['a'], 1);
      expect(decoded['b'], 'string');
      expect(decoded['c'], isTrue);
      expect(decoded['d'], isNull);
    });

    test('encodeList / decodeList 往返一致', () {
      final list = [
        {'id': 't1', 'title': '任务1'},
        {'id': 't2', 'title': '任务2'},
      ];
      final encoded = JsonCodecHelper.encodeList(list);
      final decoded = JsonCodecHelper.decodeList(encoded);
      expect(decoded.length, 2);
      expect(decoded[0]['id'], 't1');
      expect(decoded[1]['title'], '任务2');
    });

    test('decode 非 Map 抛出 FormatException', () {
      const raw = '[1, 2, 3]';
      expect(() => JsonCodecHelper.decode(raw), throwsFormatException);
    });

    test('decodeList 非 List 抛出 FormatException', () {
      const raw = '{"a": 1}';
      expect(() => JsonCodecHelper.decodeList(raw), throwsFormatException);
    });
  });

  group('SharedPreferencesLocalStorage', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    test('initialize 后可读写数据', () async {
      final storage = await SharedPreferencesLocalStorage.initialize();

      await storage.setString('key1', 'value1');
      expect(await storage.getString('key1'), 'value1');
      expect(await storage.containsKey('key1'), isTrue);
      expect(await storage.containsKey('missing'), isFalse);
    });

    test('remove 删除指定键', () async {
      final storage = await SharedPreferencesLocalStorage.initialize();
      await storage.setString('key1', 'value1');
      expect(await storage.containsKey('key1'), isTrue);

      await storage.remove('key1');
      expect(await storage.containsKey('key1'), isFalse);
      expect(await storage.getString('key1'), isNull);
    });

    test('clear 清除全部', () async {
      final storage = await SharedPreferencesLocalStorage.initialize();
      await storage.setString('k1', 'v1');
      await storage.setString('k2', 'v2');
      expect((await storage.getKeys()).length, 2);

      await storage.clear();
      expect((await storage.getKeys()).length, 0);
    });

    test('getKeys 返回所有键', () async {
      final storage = await SharedPreferencesLocalStorage.initialize();
      await storage.setString('k1', 'v1');
      await storage.setString('k2', 'v2');
      final keys = await storage.getKeys();
      expect(keys.contains('k1'), isTrue);
      expect(keys.contains('k2'), isTrue);
    });

    test('单例 initialize 多次返回相同实例', () async {
      final a = await SharedPreferencesLocalStorage.initialize();
      final b = await SharedPreferencesLocalStorage.initialize();
      expect(identical(a, b), isTrue);
    });

    test('instance 在未初始化时抛 StateError', () {
      // 通过 setTestInstance 重置单例
      SharedPreferencesLocalStorage.setTestInstance(null);
      expect(() => SharedPreferencesLocalStorage.instance, throwsStateError);
    });
  });
}
