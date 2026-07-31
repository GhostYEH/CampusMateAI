export type UserRole = 'student'

export interface User {
  name: string
  role: UserRole
  detail: string
  email: string
  studentId: string
}

export interface CampusTask {
  id: number
  title: string
  due: string
  course: string
  done: boolean
}

export interface Notice {
  id: number
  title: string
  source: string
  time: string
  unread: boolean
}

export interface Course {
  name: string
  code: string
  type: string
  teacher: string
  location: string
  weekday: string
  time: string
}

export interface ExtractResult {
  title: string
  source: string
  deadline: string
  tasks: string[]
  confidence: number
  saved?: boolean
}

export interface ChatReply {
  answer: string
  citation: string
  mock: boolean
}

export interface ChatMessage {
  id: number
  role: 'assistant' | 'user'
  text: string
  citation?: string
}

export interface AppSettings {
  mockMode: boolean
  reduceMotion: boolean
  darkMode: boolean
  remindersEnabled: boolean
  demoMode: boolean
  apiBaseUrl: string
}
