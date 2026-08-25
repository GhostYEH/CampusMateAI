export type ExpressionLabel = 'angry' | 'disgust' | 'fear' | 'happy' | 'neutral' | 'sad' | 'surprise'

export interface ExpressionFrame {
  label: string
  confidence: number
  timestamp: number
}

export interface StableExpressionSignal {
  label: ExpressionLabel
  confidence: number
  isStable: true
  timestamp: number
  modelVersion: string
}

export type ExpressionThresholds = Record<ExpressionLabel, number>

export const DEFAULT_EXPRESSION_THRESHOLDS: ExpressionThresholds = {
  angry: 0.81,
  disgust: 0.91,
  fear: 0.80,
  happy: 0.30,
  neutral: 0.83,
  sad: 0.68,
  surprise: 0.78,
}

const LABELS = Object.keys(DEFAULT_EXPRESSION_THRESHOLDS) as ExpressionLabel[]
const MAX_CHAT_SIGNAL_AGE_MS = 5_000

function isExpressionLabel(label: string): label is ExpressionLabel {
  return LABELS.includes(label as ExpressionLabel)
}

export class ExpressionSignalProcessor {
  private readonly thresholds: ExpressionThresholds
  private readonly stableFrameCount: number
  private readonly maxAgeMs: number
  private readonly modelVersion: string
  private candidateLabel: ExpressionLabel | '' = ''
  private candidateCount = 0
  private smoothedConfidence = 0
  private stableSignal?: StableExpressionSignal

  constructor(
    thresholds: ExpressionThresholds = DEFAULT_EXPRESSION_THRESHOLDS,
    stableFrameCount = 3,
    maxAgeMs = 5_000,
    modelVersion = 'wx-expression-unknown',
  ) {
    this.thresholds = thresholds
    this.stableFrameCount = Math.max(1, stableFrameCount)
    this.maxAgeMs = Math.max(0, maxAgeMs)
    this.modelVersion = modelVersion
  }

  push(frame: ExpressionFrame): StableExpressionSignal | undefined {
    if (!isExpressionLabel(frame.label)
      || !Number.isFinite(frame.confidence)
      || frame.confidence < this.thresholds[frame.label]) {
      this.resetCandidate()
      return undefined
    }

    if (this.candidateLabel === frame.label) {
      this.candidateCount += 1
      this.smoothedConfidence = 0.4 * frame.confidence + 0.6 * this.smoothedConfidence
    } else {
      this.candidateLabel = frame.label
      this.candidateCount = 1
      this.smoothedConfidence = frame.confidence
    }

    if (this.candidateCount < this.stableFrameCount) return undefined
    this.stableSignal = {
      label: frame.label,
      confidence: this.smoothedConfidence,
      isStable: true,
      timestamp: frame.timestamp,
      modelVersion: this.modelVersion,
    }
    return this.stableSignal
  }

  latest(nowMs = Date.now()): StableExpressionSignal | undefined {
    if (!this.stableSignal) return undefined
    if (nowMs - this.stableSignal.timestamp > this.maxAgeMs || nowMs < this.stableSignal.timestamp - 2_000) {
      this.stableSignal = undefined
    }
    return this.stableSignal
  }

  reset(): void {
    this.resetCandidate()
  }

  private resetCandidate(): void {
    this.candidateLabel = ''
    this.candidateCount = 0
    this.smoothedConfidence = 0
    this.stableSignal = undefined
  }
}

export function greetingForExpression(
  signal: StableExpressionSignal,
  nowMs = Date.now(),
): string | undefined {
  if (!signal.isStable || nowMs - signal.timestamp > MAX_CHAT_SIGNAL_AGE_MS || nowMs < signal.timestamp - 2_000) {
    return undefined
  }
  const greetings: Record<ExpressionLabel, string> = {
    sad: '看起来你现在可能有些难过。别一个人扛着，我在这里陪你；想聊聊，或者一起解决一件具体的事都可以。',
    angry: '看起来你现在可能有些烦躁，我们先慢一点。我会认真听你说，也可以陪你把眼前的问题一步步理清。',
    fear: '看起来你现在可能有些紧张，先别急，我们可以从最容易处理的一步开始。',
    disgust: '看起来你现在可能有些不舒服，我们可以换个轻松一点的方式慢慢聊。',
    happy: '看到你状态不错真好！我是 AI 校园助手小灵，今天想聊聊校园生活，还是一起解决一个具体问题？',
    surprise: '看起来刚才可能有件事让你有些意外。愿意的话可以告诉我，我陪你一起理清。',
    neutral: '你好，我是 AI 校园助手小灵。课程流程、奖助政策、校园服务，或者最近想聊的事，都可以告诉我。',
  }
  return greetings[signal.label]
}
