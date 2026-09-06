export enum NotificationCaptureStatus {
  SUPPORTED = 'SUPPORTED',
  NEEDS_PERMISSION = 'NEEDS_PERMISSION',
  NEEDS_DEVICE_PAIRING = 'NEEDS_DEVICE_PAIRING',
  UNAVAILABLE = 'UNAVAILABLE',
  ERROR = 'ERROR'
}

export class NotificationCaptureCapability {
  readonly status: NotificationCaptureStatus;
  readonly detail: string;

  constructor(status: NotificationCaptureStatus, detail: string) {
    this.status = status;
    this.detail = detail;
  }

  static ordinaryPhoneBuild(): NotificationCaptureCapability {
    return new NotificationCaptureCapability(
      NotificationCaptureStatus.UNAVAILABLE,
      '当前应用没有 system_basic 通知订阅资质；可使用后端通知、学习通同步或手动粘贴。'
    );
  }

  static fromUserGrant(granted: boolean): NotificationCaptureCapability {
    return granted
      ? new NotificationCaptureCapability(NotificationCaptureStatus.SUPPORTED, '系统通知监听已授权。')
      : new NotificationCaptureCapability(NotificationCaptureStatus.NEEDS_PERMISSION, '请在系统弹窗中允许获取本机通知。');
  }

  static error(detail: string): NotificationCaptureCapability {
    return new NotificationCaptureCapability(NotificationCaptureStatus.ERROR, detail);
  }

  canStart(): boolean {
    return this.status === NotificationCaptureStatus.SUPPORTED;
  }
}
