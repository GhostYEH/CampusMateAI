export interface ChaoxingStatusResponse {
  status: string;
  last_synced_at?: string;
  source?: string;
  courses?: number;
  teachers?: number;
  pending_assignments?: number;
  notices?: number;
  warnings?: string[];
}

export interface ChaoxingAccountStatus {
  rawStatus: string;
  label: string;
  connected: boolean;
  requiresLogin: boolean;
  canSync: boolean;
  lastSyncedAt: string;
  source: string;
  courses: number;
  teachers: number;
  pendingAssignments: number;
  notices: number;
  warnings: string[];
  summary: string;
}

export class ChaoxingStatusMapper {
  static fromResponse(response: ChaoxingStatusResponse): ChaoxingAccountStatus {
    const rawStatus: string = response.status || 'unavailable';
    const connected: boolean = rawStatus === 'online';
    const requiresLogin: boolean = rawStatus === 'offline' || rawStatus === 'expired';
    const courses: number = response.courses ?? 0;
    const pendingAssignments: number = response.pending_assignments ?? 0;
    const notices: number = response.notices ?? 0;
    let label: string = '暂不可用';
    if (rawStatus === 'online') label = '已连接';
    else if (rawStatus === 'expired') label = '需重新登录';
    else if (rawStatus === 'offline') label = '未连接';
    return {
      rawStatus: rawStatus,
      label: label,
      connected: connected,
      requiresLogin: requiresLogin,
      canSync: connected,
      lastSyncedAt: response.last_synced_at ?? '',
      source: response.source ?? '',
      courses: courses,
      teachers: response.teachers ?? 0,
      pendingAssignments: pendingAssignments,
      notices: notices,
      warnings: response.warnings ?? [],
      summary: `${courses} 门课程 · ${pendingAssignments} 项待交 · ${notices} 条通知`
    };
  }

  static unavailable(): ChaoxingAccountStatus {
    return ChaoxingStatusMapper.fromResponse({ status: 'unavailable' });
  }
}
