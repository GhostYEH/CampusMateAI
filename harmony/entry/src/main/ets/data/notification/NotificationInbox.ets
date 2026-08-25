import { LocalCapturedNotice } from '../Models';
import { NotificationSource, NotificationSourceResolver, NotificationSourceSettings } from './NotificationSource';

export class NotificationInbox {
  static filter(records: LocalCapturedNotice[], source: NotificationSource | null): LocalCapturedNotice[] {
    if (source === null) {
      return records;
    }
    const displayName: string = NotificationSourceResolver.sourceDisplayName(source);
    return records.filter((record: LocalCapturedNotice) => record.source_type === displayName);
  }

  static remove(records: LocalCapturedNotice[], id: string): LocalCapturedNotice[] {
    return records.filter((record: LocalCapturedNotice) => record.id !== id);
  }

  static addWhitelistGroup(groups: string[], group: string): string[] {
    const normalized: string = group.trim();
    if (normalized.length === 0 || groups.includes(normalized)) {
      return groups;
    }
    return [...groups, normalized];
  }

  static removeWhitelistGroup(groups: string[], group: string): string[] {
    return groups.filter((item: string) => item !== group);
  }

  static updateSourceSetting(settings: NotificationSourceSettings, source: NotificationSource, enabled: boolean): NotificationSourceSettings {
    return {
      wechatEnabled: source === NotificationSource.WECHAT ? enabled : settings.wechatEnabled,
      wecomEnabled: source === NotificationSource.WECOM ? enabled : settings.wecomEnabled,
      xuexitongEnabled: source === NotificationSource.XUEXITONG ? enabled : settings.xuexitongEnabled,
      qqEnabled: source === NotificationSource.QQ ? enabled : settings.qqEnabled,
      otherEnabled: settings.otherEnabled,
    };
  }
}

export class NotificationMutationQueue {
  private tail: Promise<void> = Promise.resolve();

  enqueue(operation: () => Promise<void>): Promise<void> {
    const next: Promise<void> = this.tail.then(operation, operation);
    this.tail = next.catch(() => {});
    return next;
  }

  whenIdle(): Promise<void> { return this.tail; }
}
