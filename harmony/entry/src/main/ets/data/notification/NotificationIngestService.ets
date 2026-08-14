import { CapturedNotification } from './CapturedNotification';
import { NotificationFingerprint } from './NotificationFingerprint';
import { NotificationFilter } from './NotificationFilter';
import { NotificationSource, NotificationSourceSettings, DEFAULT_SOURCE_SETTINGS } from './NotificationSource';
import { NotificationTextSanitizer } from './NotificationTextSanitizer';
import { NotificationSourceResolver } from './NotificationSource';
import { PreferencesUtil } from '../../util/PreferencesUtil';
import { ApiClient } from '../ApiClient';
import { http } from '@kit.NetworkKit';
import { NoticeIngestRequest, ExtractRequest, ExtractResult, TaskCreateRequest, TaskItem, LocalCapturedNotice, MultiNoticeExtractResponse, NoticeExtractTaskItem } from '../Models';

const FINGERPRINTS_KEY: string = 'captured_fingerprints';
const LOCAL_NOTICES_KEY: string = 'captured_local_notices';
const WECHAT_WHITELIST_KEY: string = 'captured_wechat_whitelist';
const WECOM_WHITELIST_KEY: string = 'captured_wecom_whitelist';
const QQ_WHITELIST_KEY: string = 'captured_qq_whitelist';
const SOURCE_SETTINGS_KEY: string = 'captured_source_settings';
const MAX_LOCAL_NOTICES: number = 200;

export interface IngestResult {
  success: boolean;
  fingerprint: string;
  reason: string;
}

export class NotificationIngestService {
  private readonly apiClient: ApiClient;
  private readonly tokenProvider: () => string;
  constructor(apiClient: ApiClient, tokenProvider: () => string) {
    this.tokenProvider = tokenProvider;
    this.apiClient = apiClient;
  }

  async captureAndIngest(notification: CapturedNotification): Promise<IngestResult> {
    const settings: NotificationSourceSettings = await this.loadSourceSettings();
    const wechatWhitelist: string[] = await this.loadWhitelist(WECHAT_WHITELIST_KEY);
    const wecomWhitelist: string[] = await this.loadWhitelist(WECOM_WHITELIST_KEY);
    const qqWhitelist: string[] = await this.loadWhitelist(QQ_WHITELIST_KEY);
    if (!NotificationFilter.shouldStore(notification, settings, wechatWhitelist, wecomWhitelist, qqWhitelist)) {
      return { success: false, fingerprint: '', reason: 'filtered' };
    }
    const fingerprint: string = NotificationFingerprint.create(notification);
    const isNew: boolean = await this.recordFingerprint(fingerprint);
    if (!isNew) {
      return { success: false, fingerprint: fingerprint, reason: 'duplicate' };
    }
    const primaryText: string = NotificationTextSanitizer.primaryText(notification.bigText, notification.text);
    if (primaryText.length === 0) {
      return { success: false, fingerprint: fingerprint, reason: 'empty_text' };
    }
    const sourceName: string = notification.groupCandidate.length > 0 ? notification.groupCandidate : (notification.title.length > 0 ? notification.title : NotificationSourceResolver.displayName(notification.bundleName));
    await this.saveLocalNotice(notification, fingerprint, primaryText, sourceName);
    try {
      await this.ingestToBackend(primaryText, sourceName, notification.postTime);
    } catch (e) {
      console.warn(`[NotificationIngest] backend ingest failed, kept locally: ${(e as Error).message}`);
    }
    return { success: true, fingerprint: fingerprint, reason: 'captured' };
  }

  async ingestToBackend(content: string, sourceName: string, postTime: number): Promise<void> {
    if (this.tokenProvider().length === 0) {
      return;
    }
    const publishedAt: string = new Date(postTime).toISOString();
    const payload: NoticeIngestRequest = {
      content: content,
      source_name: sourceName,
      published_at: publishedAt,
    };
    await this.apiClient.request<MultiNoticeExtractResponse>(http.RequestMethod.POST, 'notices/ingest', payload);
  }

  async extractNotice(text: string): Promise<ExtractResult> {
    try {
      const payload: ExtractRequest = { content: text };
      const response: MultiNoticeExtractResponse = await this.apiClient.request<MultiNoticeExtractResponse>(http.RequestMethod.POST, 'notices/extract-multi', payload);
      const tasks: NoticeExtractTaskItem[] = response?.tasks ?? [];
      if (tasks.length === 0) {
        return { title: '', source: '', deadline: '待设置', tasks: [], confidence: 0, error: '未提取到事务信息' };
      }
      const first: NoticeExtractTaskItem = tasks[0];
      const taskNames: string[] = tasks.map((t: NoticeExtractTaskItem) => t.task.length > 0 ? t.task : t.title);
      return {
        title: first.title.length > 0 ? first.title : (first.task.length > 0 ? first.task : ''),
        source: first.source_name ?? '',
        deadline: first.deadline ?? '待设置',
        tasks: taskNames,
        confidence: first.confidence ?? 0,
        error: '',
      };
    } catch (e) {
      return { title: '', source: '', deadline: '待设置', tasks: [], confidence: 0, error: (e as Error).message };
    }
  }

  async createTask(title: string, deadline: string, sourceName: string, description: string): Promise<TaskItem | null> {
    if (this.tokenProvider().length === 0) {
      return null;
    }
    try {
      const payload: TaskCreateRequest = {
        title: title,
        description: description.length > 0 ? description : undefined,
        deadline: deadline.length > 0 && deadline !== '待设置' ? deadline : undefined,
        source_name: sourceName.length > 0 && sourceName !== '个人待办' ? sourceName : undefined,
        priority: 'medium',
      };
      const result: TaskItem = await this.apiClient.request<TaskItem>(http.RequestMethod.POST, 'tasks', payload);
      return result;
    } catch (e) {
      console.warn(`[NotificationIngest] create task failed: ${(e as Error).message}`);
      return null;
    }
  }

  async loadLocalNotices(): Promise<LocalCapturedNotice[]> {
    const raw: string = await PreferencesUtil.getString(LOCAL_NOTICES_KEY, '');
    if (raw.length === 0) {
      return [];
    }
    try {
      return JSON.parse(raw) as LocalCapturedNotice[];
    } catch {
      return [];
    }
  }

  async clearLocalNotices(): Promise<void> {
    await PreferencesUtil.putString(LOCAL_NOTICES_KEY, '');
    await PreferencesUtil.putString(FINGERPRINTS_KEY, '');
  }

  async loadWechatWhitelist(): Promise<string[]> {
    return this.loadWhitelist(WECHAT_WHITELIST_KEY);
  }

  async loadWecomWhitelist(): Promise<string[]> { return this.loadWhitelist(WECOM_WHITELIST_KEY); }
  async loadQqWhitelist(): Promise<string[]> { return this.loadWhitelist(QQ_WHITELIST_KEY); }

  private async loadWhitelist(key: string): Promise<string[]> {
    const raw: string = await PreferencesUtil.getString(key, '');
    if (raw.length === 0) {
      return [];
    }
    try {
      return JSON.parse(raw) as string[];
    } catch {
      return [];
    }
  }

  async saveWechatWhitelist(groups: string[]): Promise<void> {
    await PreferencesUtil.putString(WECHAT_WHITELIST_KEY, JSON.stringify(groups));
  }

  async saveWecomWhitelist(groups: string[]): Promise<void> {
    await PreferencesUtil.putString(WECOM_WHITELIST_KEY, JSON.stringify(groups));
  }

  async saveQqWhitelist(groups: string[]): Promise<void> {
    await PreferencesUtil.putString(QQ_WHITELIST_KEY, JSON.stringify(groups));
  }

  async addWechatWhitelistGroup(group: string): Promise<string[]> {
    const current: string[] = await this.loadWechatWhitelist();
    if (!current.includes(group)) {
      current.push(group);
      await this.saveWechatWhitelist(current);
    }
    return current;
  }

  async removeWechatWhitelistGroup(group: string): Promise<string[]> {
    const current: string[] = await this.loadWechatWhitelist();
    const updated: string[] = current.filter((g: string) => g !== group);
    await this.saveWechatWhitelist(updated);
    return updated;
  }

  async loadSourceSettings(): Promise<NotificationSourceSettings> {
    const raw: string = await PreferencesUtil.getString(SOURCE_SETTINGS_KEY, '');
    if (raw.length === 0) {
      return DEFAULT_SOURCE_SETTINGS;
    }
    try {
      const parsed: Record<string, boolean> = JSON.parse(raw) as Record<string, boolean>;
      return {
        wechatEnabled: parsed.wechatEnabled ?? DEFAULT_SOURCE_SETTINGS.wechatEnabled,
        wecomEnabled: parsed.wecomEnabled ?? DEFAULT_SOURCE_SETTINGS.wecomEnabled,
        xuexitongEnabled: parsed.xuexitongEnabled ?? DEFAULT_SOURCE_SETTINGS.xuexitongEnabled,
        qqEnabled: parsed.qqEnabled ?? DEFAULT_SOURCE_SETTINGS.qqEnabled,
        otherEnabled: parsed.otherEnabled ?? DEFAULT_SOURCE_SETTINGS.otherEnabled,
      };
    } catch {
      return DEFAULT_SOURCE_SETTINGS;
    }
  }

  async saveSourceSettings(settings: NotificationSourceSettings): Promise<void> {
    await PreferencesUtil.putString(SOURCE_SETTINGS_KEY, JSON.stringify(settings));
  }

  private async recordFingerprint(fingerprint: string): Promise<boolean> {
    const raw: string = await PreferencesUtil.getString(FINGERPRINTS_KEY, '');
    let fingerprints: string[] = [];
    if (raw.length > 0) {
      try {
        fingerprints = JSON.parse(raw) as string[];
      } catch {
        fingerprints = [];
      }
    }
    if (fingerprints.includes(fingerprint)) {
      return false;
    }
    fingerprints.push(fingerprint);
    if (fingerprints.length > 1000) {
      fingerprints = fingerprints.slice(fingerprints.length - 1000);
    }
    await PreferencesUtil.putString(FINGERPRINTS_KEY, JSON.stringify(fingerprints));
    return true;
  }

  private async saveLocalNotice(notification: CapturedNotification, fingerprint: string, content: string, sourceName: string): Promise<void> {
    const local: LocalCapturedNotice = {
      id: fingerprint,
      title: notification.title.length > 0 ? notification.title : sourceName,
      content: content,
      source: sourceName,
      source_type: NotificationSourceResolver.sourceDisplayName(notification.source),
      time: new Date(notification.postTime).toISOString(),
      fingerprint: fingerprint,
      captured_at: Date.now(),
    };
    const existing: LocalCapturedNotice[] = await this.loadLocalNotices();
    const updated: LocalCapturedNotice[] = [local, ...existing].slice(0, MAX_LOCAL_NOTICES);
    await PreferencesUtil.putString(LOCAL_NOTICES_KEY, JSON.stringify(updated));
  }
}
