import { GroupNameNormalizer } from './GroupNameNormalizer';
import { NotificationSource } from './NotificationSource';

export interface QueuedNotification {
  id: string;
  fingerprint: string;
  source: NotificationSource;
  normalizedGroupName: string;
  text: string;
  publishedAt: number;
  retryCount: number;
}

export interface ConversationBundle {
  clientId: string;
  clientFingerprint: string;
  source: NotificationSource;
  normalizedGroupName: string;
  messages: QueuedNotification[];
  content: string;
}

export class ConversationBundler {
  static readonly BATCH_QUIET_WINDOW_MS: number = 20_000;
  static readonly BATCH_MAX_MESSAGES: number = 20;
  static readonly BATCH_MAX_CHARS: number = 4_000;
  static readonly BATCH_MAX_AGE_MS: number = 90_000;

  static bundle(rows: QueuedNotification[]): ConversationBundle[] {
    const sorted: QueuedNotification[] = [...rows].sort((a: QueuedNotification, b: QueuedNotification) => a.publishedAt - b.publishedAt);
    const grouped: Map<string, QueuedNotification[]> = new Map<string, QueuedNotification[]>();
    sorted.forEach((row: QueuedNotification) => {
      const group: string = GroupNameNormalizer.normalize(row.normalizedGroupName);
      const key: string = `${row.source}\u001F${group}`;
      const current: QueuedNotification[] = grouped.get(key) ?? [];
      current.push(row);
      grouped.set(key, current);
    });
    const result: ConversationBundle[] = [];
    grouped.forEach((groupRows: QueuedNotification[]) => {
      ConversationBundler.splitGroup(groupRows, result);
    });
    return result.sort((a: ConversationBundle, b: ConversationBundle) => a.messages[0].publishedAt - b.messages[0].publishedAt);
  }

  private static splitGroup(rows: QueuedNotification[], result: ConversationBundle[]): void {
    let current: QueuedNotification[] = [];
    let chars: number = 0;
    const flush = (): void => {
      if (current.length === 0) return;
      const group: string = GroupNameNormalizer.normalize(current[0].normalizedGroupName);
      const ids: string = current.map((row: QueuedNotification) => row.fingerprint).join('\u001F');
      result.push({
        clientId: `${current[0].source}:${group}:${current[0].id}`,
        clientFingerprint: ConversationBundler.stableFingerprint(ids),
        source: current[0].source,
        normalizedGroupName: group,
        messages: current,
        content: current.map((row: QueuedNotification) => row.text).join('\n').substring(0, ConversationBundler.BATCH_MAX_CHARS)
      });
      current = [];
      chars = 0;
    };
    rows.forEach((row: QueuedNotification) => {
      const gap: number = current.length === 0 ? 0 : row.publishedAt - current[current.length - 1].publishedAt;
      const age: number = current.length === 0 ? 0 : row.publishedAt - current[0].publishedAt;
      if (current.length > 0 && (gap > ConversationBundler.BATCH_QUIET_WINDOW_MS || age > ConversationBundler.BATCH_MAX_AGE_MS ||
        current.length >= ConversationBundler.BATCH_MAX_MESSAGES || chars + row.text.length + 1 > ConversationBundler.BATCH_MAX_CHARS)) {
        flush();
      }
      current.push(row);
      chars += row.text.length + 1;
    });
    flush();
  }

  private static stableFingerprint(value: string): string {
    let hash: number = 2166136261;
    for (let i: number = 0; i < value.length; i++) {
      hash ^= value.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16).padStart(8, '0');
  }
}
