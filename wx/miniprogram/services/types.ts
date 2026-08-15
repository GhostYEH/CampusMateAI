export type UserRole = 'student'

export interface User {
  name: string
  role: UserRole
  detail: string
  email: string
  studentId: string
}

export interface CampusTask {
  id: number | string
  title: string
  due: string
  deadline?: string
  course: string
  done: boolean
  priority?: 'low' | 'medium' | 'high'
}

export interface Notice {
  id: number | string
  title: string
  source: string
  time: string
  unread: boolean
}

export interface Course {
  id?: string
  name: string
  code: string
  type: string
  teacher: string
  location: string
  weekday: string
  time: string
}

export interface ExtractResult {
  id: string
  title: string
  source: string
  deadline: string
  rawDeadline?: string
  sourceText?: string
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

export interface ConnectionState {
  mode: 'remote' | 'mock'
  apiBaseUrl: string
  authenticated: boolean
}

export interface BackendHealth {
  status: string
  mode: string
  version?: string
}

export interface WeekDay {
  label: string
  date: number
  active: boolean
}
