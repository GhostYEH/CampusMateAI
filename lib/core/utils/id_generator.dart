import 'package:uuid/uuid.dart';

/// ID 生成器。
class IdGenerator {
  IdGenerator._();
  static const _uuid = Uuid();

  static String newId([String prefix = 'id']) {
    return '${prefix}_${_uuid.v4().substring(0, 8)}';
  }
}
