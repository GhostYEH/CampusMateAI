export enum NotificationSource {
  WECHAT = 'wechat',
  XUEXITONG = 'xuexitong',
  QQ = 'qq',
  OTHER = 'other',
}

export interface NotificationSourceSettings {
  wechatEnabled: boolean;
  xuexitongEnabled: boolean;
  qqEnabled: boolean;
  otherEnabled: boolean;
}

export const DEFAULT_SOURCE_SETTINGS: NotificationSourceSettings = {
  wechatEnabled: true,
  xuexitongEnabled: true,
  qqEnabled: false,
  otherEnabled: false,
};

const WECHAT_PACKAGE: string = 'com.tencent.mm';
const XUEXITONG_PACKAGE: string = 'com.chaoxing.mobile';
const QQ_PACKAGES: string[] = ['com.tencent.mobileqq', 'com.tencent.qqlite', 'com.tencent.tim'];

export class NotificationSourceResolver {
  static resolve(bundleName: string): NotificationSource {
    if (bundleName === WECHAT_PACKAGE) {
      return NotificationSource.WECHAT;
    }
    if (bundleName === XUEXITONG_PACKAGE) {
      return NotificationSource.XUEXITONG;
    }
    if (QQ_PACKAGES.includes(bundleName)) {
      return NotificationSource.QQ;
    }
    return NotificationSource.OTHER;
  }

  static displayName(bundleName: string): string {
    const source: NotificationSource = NotificationSourceResolver.resolve(bundleName);
    return NotificationSourceResolver.sourceDisplayName(source);
  }

  static sourceDisplayName(source: NotificationSource): string {
    switch (source) {
      case NotificationSource.WECHAT: return '微信';
      case NotificationSource.XUEXITONG: return '学习通';
      case NotificationSource.QQ: return 'QQ';
      case NotificationSource.OTHER: return '其他应用';
      default: return '其他应用';
    }
  }
}

export function isSourceEnabled(settings: NotificationSourceSettings, source: NotificationSource): boolean {
  switch (source) {
    case NotificationSource.WECHAT: return settings.wechatEnabled;
    case NotificationSource.XUEXITONG: return settings.xuexitongEnabled;
    case NotificationSource.QQ: return settings.qqEnabled;
    case NotificationSource.OTHER: return settings.otherEnabled;
    default: return false;
  }
}
