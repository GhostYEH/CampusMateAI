export class GroupNameNormalizer {
  static normalize(value: string): string {
    let normalized: string = value.trim()
      .replace(/\u3000/g, ' ')
      .replace(/（/g, '(')
      .replace(/）/g, ')')
      .replace(/[\t\r\n ]+/g, ' ');
    normalized = normalized.replace(/\s*\(\s*\d+\s*条(?:新)?消息\s*\)\s*$/, '');
    normalized = normalized.replace(/\s*\(\s*\d+\s*\)\s*$/, '');
    normalized = normalized.replace(/\s+\d+\s*条(?:新)?消息\s*$/, '');
    return normalized.trim();
  }

  static matches(candidate: string, whitelist: string[]): boolean {
    const normalizedCandidate: string = GroupNameNormalizer.normalize(candidate);
    if (normalizedCandidate.length === 0) {
      return false;
    }
    return whitelist.some((entry: string) => GroupNameNormalizer.normalize(entry) === normalizedCandidate);
  }
}
