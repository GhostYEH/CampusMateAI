export enum NotificationSource {
  WECHAT = 'wechat',
  WECOM = 'wecom',
  XUEXITONG = 'xuexitong',
  QQ = 'qq',
  OTHER = 'other',
}

export interface NotificationSourceSettings {
  wechatEnabled: boolean;
  wecomEnabled: boolean;
  xuexitongEnabled: boolean;
  qqEnabled: boolean;
  otherEnabled: boolean;
}

export const DEFAULT_SOURCE_SETTINGS: NotificationSourceSettings = {
  wechatEnabled: true,
  wecomEnabled: true,
  xuexitongEnabled: true,
  qqEnabled: false,
  otherEnabled: false,
};

export class NotificationSourceAliasRegistry {
  private readonly aliases: Map<string, NotificationSource> = new Map<string, NotificationSource>();

  static defaults(): NotificationSourceAliasRegistry {
    const registry: NotificationSourceAliasRegistry = new NotificationSourceAliasRegistry();
    registry.registerVerifiedAlias(NotificationSource.WECHAT, 'com.tencent.mm');
    registry.registerVerifiedAlias(NotificationSource.WECOM, 'com.tencent.wework');
    registry.registerVerifiedAlias(NotificationSource.XUEXITONG, 'com.chaoxing.mobile');
    registry.registerVerifiedAlias(NotificationSource.QQ, 'com.tencent.mobileqq');
    registry.registerVerifiedAlias(NotificationSource.QQ, 'com.tencent.qqlite');
    registry.registerVerifiedAlias(NotificationSource.QQ, 'com.tencent.tim');
    return registry;
  }

  registerVerifiedAlias(source: NotificationSource, bundleName: string): void {
    const normalized: string = bundleName.trim();
    if (normalized.length > 0) {
      this.aliases.set(normalized, source);
    }
  }

  resolve(bundleName: string): NotificationSource {
    return this.aliases.get(bundleName) ?? NotificationSource.OTHER;
  }
}

const DEFAULT_ALIAS_REGISTRY: NotificationSourceAliasRegistry = NotificationSourceAliasRegistry.defaults();

export class NotificationSourceResolver {
  static resolve(bundleName: string, registry: NotificationSourceAliasRegistry = DEFAULT_ALIAS_REGISTRY): NotificationSource {
    return registry.resolve(bundleName);
  }

  static displayName(bundleName: string): string {
    const source: NotificationSource = NotificationSourceResolver.resolve(bundleName);
    return NotificationSourceResolver.sourceDisplayName(source);
  }

  static sourceDisplayName(source: NotificationSource): string {
    switch (source) {
      case NotificationSource.WECHAT: return '微信';
      case NotificationSource.WECOM: return '企业微信';
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
    case NotificationSource.WECOM: return settings.wecomEnabled;
    case NotificationSource.XUEXITONG: return settings.xuexitongEnabled;
    case NotificationSource.QQ: return settings.qqEnabled;
    case NotificationSource.OTHER: return settings.otherEnabled;
    default: return false;
  }
}
