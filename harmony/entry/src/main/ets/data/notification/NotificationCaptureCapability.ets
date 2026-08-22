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
      '普通手机应用没有 system_basic 通知订阅权限；可使用后端通知、学习通同步或手动粘贴。'
    );
  }

  canStart(): boolean {
    return this.status === NotificationCaptureStatus.SUPPORTED;
  }
}
