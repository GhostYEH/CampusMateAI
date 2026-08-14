export class ApiResponseParser {
  static parseRequired<T>(raw: string): T {
    if (raw.trim().length === 0) {
      throw new Error('服务器返回空数据');
    }
    try {
      return JSON.parse(raw) as T;
    } catch (_) {
      throw new Error('服务器返回数据格式错误');
    }
  }

  static parseOptional<T>(raw: string): T | undefined {
    if (raw.trim().length === 0) {
      return undefined;
    }
    return ApiResponseParser.parseRequired<T>(raw);
  }
}
