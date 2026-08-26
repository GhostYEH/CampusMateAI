export type CpmMessageRole = 'user' | 'assistant'
export type CpmMessageStatus = 'GENERATING' | 'COMPLETED' | 'ERROR'

export interface CpmChatMessage {
  id: string
  role: CpmMessageRole
  text: string
  status: CpmMessageStatus
  citation?: string
  errorMessage?: string
}

export interface CpmPrompt {
  id: string
  label: string
  prompt: string
  icon: string
}

export interface CpmCounselorState {
  messages: CpmChatMessage[]
  input: string
  sending: boolean
  chatActive: boolean
  recommendationOffset: number
  recommendations: CpmPrompt[]
  speechText: string
  speechRequestId: number
  lastPrompt: string
}

const PROMPTS: CpmPrompt[] = [
  { id: 'freshman', label: '大一应该\n怎么规划', prompt: '大一应该怎么规划？', icon: '/assets/icons/service-academic.svg' },
  { id: 'graduate', label: '我应该读研\n还是就业', prompt: '我应该读研还是就业？', icon: '/assets/icons/tab-courses-active-light.svg' },
  { id: 'club', label: '社团应该\n怎么选', prompt: '社团应该怎么选？', icon: '/assets/icons/service-community.svg' },
  { id: 'balance', label: '怎么平衡\n学习和生活', prompt: '怎么平衡学习和生活？', icon: '/assets/icons/service-study.svg' },
  { id: 'internship', label: '大学期间如何\n准备实习', prompt: '大学期间应该如何准备实习？', icon: '/assets/icons/service-account.svg' },
  { id: 'direction', label: '找不到方向\n怎么办', prompt: '大学里暂时找不到方向怎么办？', icon: '/assets/icons/service-academic.svg' },
  { id: 'friendship', label: '怎样建立健康的\n同学关系', prompt: '怎样建立健康的同学关系？', icon: '/assets/icons/service-community.svg' },
  { id: 'habits', label: '如何养成稳定的\n学习习惯', prompt: '如何养成稳定的学习习惯？', icon: '/assets/icons/service-study.svg' },
]

function promptBatch(offset: number): CpmPrompt[] {
  return Array.from({ length: 4 }, (_, index) => PROMPTS[(offset + index) % PROMPTS.length])
}

export function createCpmState(): CpmCounselorState {
  return {
    messages: [], input: '', sending: false, chatActive: false,
    recommendationOffset: 0, recommendations: promptBatch(0),
    speechText: '', speechRequestId: 0, lastPrompt: '',
  }
}

export function shouldShowCpmSuggestions(state: CpmCounselorState): boolean {
  return !state.chatActive && state.messages.length === 0
}

export function shuffleCpmRecommendations(state: CpmCounselorState): CpmCounselorState {
  const recommendationOffset = (state.recommendationOffset + 4) % PROMPTS.length
  return { ...state, recommendationOffset, recommendations: promptBatch(recommendationOffset) }
}

export function submitCpmQuestion(state: CpmCounselorState, rawQuestion: string, now: number): CpmCounselorState {
  const question = rawQuestion.trim()
  if (!question || state.sending) return state
  return {
    ...state,
    messages: [
      ...state.messages,
      { id: `user-${now}`, role: 'user', text: question, status: 'COMPLETED' },
      { id: `assistant-${now}`, role: 'assistant', text: '', status: 'GENERATING' },
    ],
    input: '', sending: true, chatActive: true, lastPrompt: question,
  }
}

export function completeCpmAnswer(
  state: CpmCounselorState,
  assistantId: string,
  answer: string,
  citation = '校园知识库',
): CpmCounselorState {
  const text = answer.trim() || '暂无回答'
  return {
    ...state,
    messages: state.messages.map((message) => message.id === assistantId
      ? { ...message, text, status: 'COMPLETED', citation }
      : message),
    sending: false,
    speechText: text,
    speechRequestId: state.speechRequestId + 1,
  }
}

export function failCpmAnswer(state: CpmCounselorState, assistantId: string, errorMessage: string): CpmCounselorState {
  return {
    ...state,
    messages: state.messages.map((message) => message.id === assistantId
      ? { ...message, text: message.text || '暂时无法生成回答，请稍后重试。', status: 'ERROR', errorMessage }
      : message),
    sending: false,
  }
}
