export type NotificationSource = 'wechat' | 'wecom' | 'qq' | 'xuexitong' | 'campus' | 'other'
export type NotificationFilter = NotificationSource | 'all'

export interface NotificationInboxRecord {
  id: string
  fingerprint: string
  source: NotificationSource
  sourceName: string
  title: string
  content: string
  capturedAt: number
  unread: boolean
}

const STORAGE_KEY = 'campus.notification-inbox.v1'
const MAX_RECORDS = 100

function normalize(value: string): string {
  return value.replace(/[\u3000\s]+/g, ' ').trim()
}

function hash(value: string): string {
  let result = 2166136261
  for (let index = 0; index < value.length; index += 1) {
    result ^= value.charCodeAt(index)
    result = Math.imul(result, 16777619)
  }
  return (result >>> 0).toString(16).padStart(8, '0')
}

export function classifyNotificationSource(title: string, content: string): NotificationSource {
  const value = `${title} ${content}`.toLowerCase()
  if (/企业微信|wecom/.test(value)) return 'wecom'
  if (/学习通|超星|xuexitong|chaoxing/.test(value)) return 'xuexitong'
  if (/(^|\s)qq(\s|$)|qq群|tim/.test(value)) return 'qq'
  if (/微信|微信群/.test(value)) return 'wechat'
  if (/教务|学院|校园|学校|辅导员|课程|选课|考试/.test(value)) return 'campus'
  return 'other'
}

export function createInboxRecord(
  sourceName: string,
  title: string,
  content: string,
  capturedAt = Date.now(),
): NotificationInboxRecord {
  const normalizedSource = normalize(sourceName) || '手动导入'
  const normalizedTitle = normalize(title) || '未命名通知'
  const normalizedContent = normalize(content)
  const fingerprint = hash(`${normalizedSource.toLowerCase()}|${normalizedTitle.toLowerCase()}|${normalizedContent.toLowerCase()}`)
  return {
    id: `${capturedAt}-${fingerprint}`,
    fingerprint,
    source: classifyNotificationSource(normalizedSource, `${normalizedTitle} ${normalizedContent}`),
    sourceName: normalizedSource,
    title: normalizedTitle,
    content: normalizedContent,
    capturedAt,
    unread: true,
  }
}

export function upsertInboxRecord(
  records: NotificationInboxRecord[],
  incoming: NotificationInboxRecord,
): NotificationInboxRecord[] {
  const withoutDuplicate = records.filter((record) => record.fingerprint !== incoming.fingerprint)
  return [incoming, ...withoutDuplicate].sort((left, right) => right.capturedAt - left.capturedAt).slice(0, MAX_RECORDS)
}

export function filterInboxRecords(
  records: NotificationInboxRecord[],
  source: NotificationFilter,
  query: string,
): NotificationInboxRecord[] {
  const keyword = normalize(query).toLowerCase()
  return records.filter((record) => {
    const sourceMatches = source === 'all' || record.source === source
    const queryMatches = !keyword || `${record.sourceName} ${record.title} ${record.content}`.toLowerCase().includes(keyword)
    return sourceMatches && queryMatches
  })
}

export function removeInboxRecord(records: NotificationInboxRecord[], id: string): NotificationInboxRecord[] {
  return records.filter((record) => record.id !== id)
}

export function addWhitelistGroup(groups: string[], group: string): string[] {
  const normalized = normalize(group)
  return !normalized || groups.includes(normalized) ? groups : [...groups, normalized]
}

export class NotificationInboxStore {
  load(): NotificationInboxRecord[] {
    const stored = wx.getStorageSync(STORAGE_KEY) as NotificationInboxRecord[] | ''
    return Array.isArray(stored) ? stored : []
  }

  save(records: NotificationInboxRecord[]): void {
    wx.setStorageSync(STORAGE_KEY, records.slice(0, MAX_RECORDS))
  }

  add(record: NotificationInboxRecord): NotificationInboxRecord[] {
    const records = upsertInboxRecord(this.load(), record)
    this.save(records)
    return records
  }

  remove(id: string): NotificationInboxRecord[] {
    const records = removeInboxRecord(this.load(), id)
    this.save(records)
    return records
  }

  clear(): void {
    wx.removeStorageSync(STORAGE_KEY)
  }
}
