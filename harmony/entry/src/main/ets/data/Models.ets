export interface TaskItem { id: string; title: string; description?: string; deadline?: string; due?: string; priority?: string; status?: string; source_name?: string; }
export interface NoticeItem { id: string; title: string; source?: string; time?: string; unread?: boolean; content?: string; }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; }
export interface CourseItem { id: string; name: string; code?: string; teacher_name?: string; semester?: string; description?: string; status?: string; }
export interface ActivityItem { id: string; title: string; summary?: string; content?: string; category?: string; location?: string; starts_at?: string; author_name?: string; status?: string; capacity?: number; }
export interface PagedResponse<T> { items: T[]; total: number; page: number; page_size: number; has_more: boolean; }
export interface UserItem { id?: string; username?: string; name?: string; display_name?: string; role?: string; detail?: string; college?: string; major?: string; grade?: string; }
export interface MeResponse { user: UserItem; }
export interface ChatResponse { answer?: string; message?: string; }
export interface ChatRequest { message: string; session_id: string; stream: boolean; }
export interface ExamItem { id: string; course_name: string; exam_date: string; start_time?: string; end_time?: string; location?: string; seat_number?: string; exam_type?: string; reminder_enabled?: boolean; notes?: string; }
export interface ClassroomItem { id?: string; name?: string; building?: string; capacity?: number; has_multimedia?: boolean; }
export interface ClassroomAvailability { classroom?: ClassroomItem; id?: string; name?: string; building?: string; capacity?: number; has_multimedia?: boolean; free_slots?: string[]; }
export interface ClassroomResponse { items: ClassroomAvailability[]; total: number; date?: string; building?: string; source?: string; }
export interface ServiceRequestItem { id: string; kind: string; title: string; content?: string; status: string; created_at: string; updated_at?: string; }
export interface ServiceRequestPayload { kind: string; title: string; content: string; }
export interface LostFoundItem { id: string; owner_id?: string; kind: string; title: string; content?: string; location?: string; contact?: string; status?: string; created_at?: string; }
export interface LostFoundPayload { kind: string; title: string; content: string; location: string; contact: string; }
export interface StudySession { id: string; goal?: string; started_at: string; ended_at?: string; duration_seconds: number; pause_seconds: number; status: string; created_at?: string; }
export interface StudySessionCreate { goal: string; }
export interface StudySessionFinish { self_report?: string; self_report_tags?: string[]; }
export interface PersonalFileItem { id: string; name: string; category?: string; size_label?: string; updated_at?: string; source?: string; is_favorite?: boolean; }
export interface PersonalFileCreate { name: string; category: string; source: string; size_label: string; }
export interface FavoriteItem { id: string; title: string; type?: string; subtitle?: string; saved_at?: string; source_route?: string; }
