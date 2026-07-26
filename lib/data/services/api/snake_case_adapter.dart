/// snake_case ↔ camelCase 转换工具 — 用于后端字段命名约定适配。
///
/// 后端使用 snake_case(如 `course_id`),Dart 模型内部使用 camelCase(如 `courseId`)。
/// 各 [ApiXxxService] 实现负责在请求 / 响应边界进行字段转换。
///
/// Dart 模型 `fromJson` 大多已支持同时识别 snake_case 和 camelCase,
/// 因此响应方向通常无需额外处理。请求方向需要主动转换为 snake_case,
/// 以匹配后端约定。
class SnakeCaseAdapter {
  SnakeCaseAdapter._();

  /// 将 camelCase 字符串转为 snake_case。
  ///
  /// 示例: `courseId` → `course_id`,`studentIdNo` → `student_id_no`。
  static String toSnake(String camel) {
    final sb = StringBuffer();
    for (var i = 0; i < camel.length; i++) {
      final ch = camel[i];
      if (ch.toUpperCase() == ch && ch.toLowerCase() != ch) {
        // 大写字母 → 前置下划线 + 小写
        if (i > 0) sb.write('_');
        sb.write(ch.toLowerCase());
      } else {
        sb.write(ch);
      }
    }
    return sb.toString();
  }

  /// 将 Map 的所有 key 从 camelCase 转为 snake_case(递归)。
  ///
  /// 用于将 Dart 模型 `toJson()` 输出(默认 camelCase)转为后端期望的 snake_case。
  static Map<String, dynamic> toSnakeKeys(Map<String, dynamic> input) {
    final out = <String, dynamic>{};
    input.forEach((key, value) {
      final newKey = toSnake(key);
      out[newKey] = _convertValue(value);
    });
    return out;
  }

  /// 将 List 中的每个 Map 元素也递归转换。
  static dynamic _convertValue(dynamic value) {
    if (value is Map<String, dynamic>) {
      return toSnakeKeys(value);
    }
    if (value is List) {
      return value.map((e) {
        if (e is Map<String, dynamic>) return toSnakeKeys(e);
        return e;
      }).toList();
    }
    return value;
  }

  /// 将 snake_case 字符串转为 camelCase。
  static String toCamel(String snake) {
    final sb = StringBuffer();
    var nextUpper = false;
    for (var i = 0; i < snake.length; i++) {
      final ch = snake[i];
      if (ch == '_') {
        nextUpper = true;
        continue;
      }
      if (nextUpper) {
        sb.write(ch.toUpperCase());
        nextUpper = false;
      } else {
        sb.write(ch);
      }
    }
    return sb.toString();
  }

  /// 将 Map 的所有 key 从 snake_case 转为 camelCase(递归)。
  static Map<String, dynamic> toCamelKeys(Map<String, dynamic> input) {
    final out = <String, dynamic>{};
    input.forEach((key, value) {
      final newKey = toCamel(key);
      out[newKey] = _convertValueToCamel(value);
    });
    return out;
  }

  static dynamic _convertValueToCamel(dynamic value) {
    if (value is Map<String, dynamic>) {
      return toCamelKeys(value);
    }
    if (value is List) {
      return value.map((e) {
        if (e is Map<String, dynamic>) return toCamelKeys(e);
        return e;
      }).toList();
    }
    return value;
  }
}
