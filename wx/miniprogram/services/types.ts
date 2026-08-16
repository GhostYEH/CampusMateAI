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

export interface StudentExam {
  id: string
  course_name: string
  exam_date: string
  start_time?: string
  end_time?: string
  location?: string
  seat_number?: string
  exam_type?: string
  reminder_enabled: boolean
  notes?: string
}

export interface Classroom {
  id?: string
  building?: string
  room?: string
  capacity?: number
  available_slots?: string[]
}

export interface CommunityPost {
  id: string
  title: string
  content: string
  author_id?: string
  author_name: string
  category: string
  images?: string[]
  extra?: Record<string, unknown>
  is_anonymous?: boolean
  status?: string
  like_count: number
  comment_count: number
  favorite_count: number
  view_count?: number
  liked?: boolean
  favorited?: boolean
  is_owner?: boolean
  created_at: string
  updated_at?: string
}

export interface CommunityComment {
  id: string
  post_id: string
  author_id?: string
  author_name: string
  parent_comment_id?: string
  content: string
  is_anonymous?: boolean
  status?: string
  created_at: string
}

export interface CategoryMeta {
  key: string
  label: string
  description: string
  icon: string
  color: string
}

export interface LostFoundItem {
  id: string
  owner_id: string
  kind: 'lost' | 'found'
  title: string
  content?: string
  location?: string
  contact?: string
  contact_visibility: 'private' | 'public'
  status: string
  created_at: string
}

export interface CampusActivity {
  id: string
  title: string
  summary?: string
  location?: string
  start_time?: string
  registration_deadline?: string
  capacity?: number
}

export interface PersonalFile {
  id: string
  name: string
  category: string
  size_label?: string
  updated_at: string
  source?: string
  is_favorite: boolean
}

export interface FavoriteItem {
  id: string
  title: string
  type: string
  subtitle?: string
  saved_at: string
  source_route?: string
}

export interface University {
  id: string
  name: string
  city?: string
  province?: string
}

export interface ServiceRequest {
  id: string
  kind: string
  title: string
  content?: string
  status: string
  created_at: string
}

export interface WeekDay {
  label: string
  date: number
  active: boolean
}
