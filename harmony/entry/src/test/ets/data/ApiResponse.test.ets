import { describe, expect, it } from '@ohos/hypium';
import { ApiResponseParser } from '../../../main/ets/data/ApiResponse';

export default function apiResponseTest(): void {
  describe('ApiResponseParser', () => {
    it('extracts structured error codes without guessing from malformed bodies', 0, () => {
      expect(ApiResponseParser.errorCode('{"code":"CHAOXING_CREDENTIALS_UNAVAILABLE"}')).assertEqual('CHAOXING_CREDENTIALS_UNAVAILABLE');
      expect(ApiResponseParser.errorCode('null')).assertEqual('');
      expect(ApiResponseParser.errorCode('<html>Unavailable</html>')).assertEqual('');
      expect(ApiResponseParser.errorCode('{"code":123}')).assertEqual('');
    });
    it('returns undefined for a successful empty response instead of parsing JSON', 0, () => {
      expect(ApiResponseParser.parseOptional<object>('')).assertUndefined();
    });

    it('parses a non-empty JSON response', 0, () => {
      const parsed: Record<string, string> | undefined =
        ApiResponseParser.parseOptional<Record<string, string>>('{"ok":"yes"}');
      expect(parsed?.ok).assertEqual('yes');
    });
  });
}
