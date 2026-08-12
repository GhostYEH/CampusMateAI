import { NotificationTextSanitizer } from './NotificationTextSanitizer';

export enum ClassificationKind { ACCEPT = 'accept', IGNORE = 'ignore' }

export interface Classification {
  kind: ClassificationKind;
  reason: string;
}

const NON_TASK_KEYWORDS: string[] = [
  '微信支付', '转账成功', '付款成功', '支付成功',
  '验证码', '验证码是', '校验码',
  '快递已到', '菜鸟驿站', '取件码', '凭取件码',
  '优惠券', '领取红包', '拼团成功',
  '已提交', '已完成', '已批阅', '提交成功', '报名成功', '申请成功',
  '好友申请', '申请加为好友', '我报名了', '已经报名',
  '哈哈哈', '呵呵呵', '笑死',
];

const NON_TASK_REGEXES: RegExp[] = [
  new RegExp('^[嗯好哦OKok行对是的]{1,3}$'),
  new RegExp('^(晚上|中午|早上|今天|明天).{0,4}(吃|喝|去|玩|走|到|回)'),
  new RegExp('^(在吗|在不在|到了吗|到哪了|回了吗|起了吗|睡了吗|下班了吗|下课了吗|到宿舍了吗|到宿舍了没)'),
  new RegExp('^\\d+条新消息$'),
  new RegExp('^(已读|已收到|收到|明白|了解|知道|好的收到|嗯嗯|好嘞|行吧|可以|没问题)'),
  new RegExp('(一起|约着?).{0,8}(吃饭|聚餐|喝酒|喝奶茶|出去玩|开黑|去操场)'),
];

const TASK_KEYWORDS: string[] = [
  '截止', '提交', '作业', '实验', '报告', '考试', '报名', '申请',
  'deadline', 'DDL', 'ddl', '期末', '期中', 'quiz', 'Quiz',
  '论文', '答辩', '开题', '实习', '实践', '选课', '退课',
  '预约', '借阅', '归还', '签到', '打卡', '上交',
];

const CAMPUS_AFFAIRS_KEYWORDS: string[] = [
  '教务', '课程', '班委', '班会', '学院', '辅导员', '奖学金', '助学金',
  '评议', '学分', '成绩', '四六级', '毕业', '开学', '返校', '离校',
  '宿舍', '校园',
];

const ACTION_SIGNAL_WORDS: string[] = ['请', '务必', '需要', '尽快', '注意', '查看', '完成', '参加'];
const ACTION_SIGNAL_REGEX: RegExp = new RegExp('((今天|明天)(上午|下午|晚上|早上|中午)|本周|下周|周[一二三四五六日天]|\\d{1,2}[:：点时])');

export class NotificationContentClassifier {
  static classify(text: string | undefined | null): Classification {
    const cleaned: string = NotificationTextSanitizer.clean(text);
    if (cleaned.length === 0) {
      return { kind: ClassificationKind.IGNORE, reason: '空内容' };
    }
    if (cleaned.length < 4) {
      return { kind: ClassificationKind.IGNORE, reason: '内容过短' };
    }
    const hardExclusion: string | null = NotificationContentClassifier.hardExclusionReason(cleaned);
    if (hardExclusion !== null) {
      return { kind: ClassificationKind.IGNORE, reason: hardExclusion };
    }
    for (const kw of TASK_KEYWORDS) {
      if (cleaned.includes(kw)) {
        return { kind: ClassificationKind.ACCEPT, reason: `事务关键词: ${kw}` };
      }
    }
    for (const kw of CAMPUS_AFFAIRS_KEYWORDS) {
      if (cleaned.includes(kw) && NotificationContentClassifier.hasActionSignal(cleaned)) {
        return { kind: ClassificationKind.ACCEPT, reason: `校园事务关键词: ${kw}` };
      }
    }
    return { kind: ClassificationKind.IGNORE, reason: '未发现校园事务特征' };
  }

  static isLikelyNonTask(text: string | undefined | null): boolean {
    return NotificationContentClassifier.classify(text).kind === ClassificationKind.IGNORE;
  }

  static isHardExcluded(text: string | undefined | null): boolean {
    const cleaned: string = NotificationTextSanitizer.clean(text);
    if (cleaned.length === 0) {
      return false;
    }
    return NotificationContentClassifier.hardExclusionReason(cleaned) !== null;
  }

  static hasActionSignal(text: string | undefined | null): boolean {
    const cleaned: string = NotificationTextSanitizer.clean(text);
    if (cleaned.length === 0) {
      return false;
    }
    for (const word of ACTION_SIGNAL_WORDS) {
      if (cleaned.includes(word)) {
        return true;
      }
    }
    return ACTION_SIGNAL_REGEX.test(cleaned);
  }

  private static hardExclusionReason(cleaned: string): string | null {
    for (const kw of NON_TASK_KEYWORDS) {
      if (cleaned.includes(kw)) {
        return `非事务关键词: ${kw}`;
      }
    }
    for (const regex of NON_TASK_REGEXES) {
      if (regex.test(cleaned)) {
        return '非事务模式匹配';
      }
    }
    return null;
  }
}