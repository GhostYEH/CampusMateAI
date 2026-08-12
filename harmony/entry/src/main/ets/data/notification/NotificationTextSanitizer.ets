export class NotificationTextSanitizer {
  static clean(value: string | undefined | null): string {
    if (value === null || value === undefined) {
      return '';
    }
    return value.replace(/\s+/g, ' ').trim();
  }

  static primaryText(bigText: string, text: string): string {
    const cleanedBig: string = NotificationTextSanitizer.clean(bigText);
    if (cleanedBig.length > 0) {
      return cleanedBig;
    }
    return NotificationTextSanitizer.clean(text);
  }

  static joinedLines(lines: string[] | undefined | null): string {
    if (lines === null || lines === undefined || lines.length === 0) {
      return '';
    }
    const cleaned: string[] = [];
    const seen: Set<string> = new Set<string>();
    for (const line of lines) {
      const c: string = NotificationTextSanitizer.clean(line);
      if (c.length > 0 && !seen.has(c)) {
        seen.add(c);
        cleaned.push(c);
      }
    }
    return cleaned.join('\n');
  }
}