export interface TaskItem { id: string; title: string; description?: string; deadline?: string; due?: string; priority?: string; importance?: string; status?: string; source_name?: string; }
export interface NoticeItem { id: string; title: string; source?: string; time?: string; unread?: boolean; content?: string; }
export interface ChatMessage { id: string; role: 'user' | 'assistant'; content: string; }
export class ChatMessageModel {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  constructor(id: string, role: 'user' | 'assistant', content: string) { this.id = id; this.role = role; this.content = content; }
}
export interface MarkdownLine { id: string; text: string; }
export interface CourseItem { id: string; name: string; code?: string; teacher_name?: string; semester?: string; description?: string; status?: string; provider?: string; external_id?: string; last_synced_at?: string; }
export interface CourseContentItem { id: string; external_id: string; kind: string; title: string; parent_external_id?: string; description?: string; author_name?: string; status?: string; deadline?: string; published_at?: string; mime_type?: string; cached?: boolean; can_download?: boolean; can_open?: boolean; }
export interface CourseSectionStatus { section: string; status: string; item_count: number; last_synced_at?: string; error_code?: string; }
export interface CourseContentSummary { course_id: string; provider?: string; cover_url?: string; teacher_name?: string; school_name?: string; class_name?: string; student_count?: number; sections: CourseSectionStatus[]; }
export interface CourseContentPage { items: CourseContentItem[]; total: number; page: number; page_size: number; has_more: boolean; }
export interface CourseContentBundle { summary?: CourseContentSummary; items: CourseContentItem[]; }
export interface ActivityItem { id: string; title: string; summary?: string; content?: string; category?: string; location?: string; starts_at?: string; author_name?: string; status?: string; capacity?: number; }
export interface PagedResponse<T> { items: T[]; total: number; page: number; page_size: number; has_more: boolean; }
export interface UserItem { id?: string; username?: string; name?: string; display_name?: string; role?: string; detail?: string; college?: string; major?: string; grade?: string; university_id?: string; university_name?: string; }
export interface MeResponse { user: UserItem; }
export interface ChatResponse { answer?: string; message?: string; }
export interface ExpressionSignalRequest { label: string; confidence: number; is_stable: boolean; timestamp: number; model_version: string; }
export interface ChatRequest { message: string; session_id: string; stream: boolean; expression_signal?: ExpressionSignalRequest; }
export interface ExamItem { id: string; course_name: string; exam_date: string; start_time?: string; end_time?: string; location?: string; seat_number?: string; exam_type?: string; reminder_enabled?: boolean; notes?: string; }
export interface ClassroomItem { id?: string; name?: string; building?: string; capacity?: number; has_multimedia?: boolean; }
export interface ClassroomAvailability { classroom?: ClassroomItem; id?: string; name?: string; building?: string; capacity?: number; has_multimedia?: boolean; free_slots?: string[]; }
export interface ClassroomResponse { items: ClassroomAvailability[]; total: number; date?: string; building?: string; source?: string; }
export interface ServiceRequestItem { id: string; kind: string; title: string; content?: string; status: string; created_at: string; updated_at?: string; }
export interface ServiceRequestPayload { kind: string; title: string; content: string; }
export interface LostFoundItem { id: string; owner_id?: string; kind: string; title: string; content?: string; location?: string; contact?: string; status?: string; created_at?: string; }
export interface LostFoundPayload { kind: string; title: string; content: string; location: string; contact: string; }
export type FocusMode = 'focus' | 'short_break' | 'long_break';
export interface StudySession { id: string; mode: FocusMode; goal?: string; related_task_id?: string; started_at: string; paused_at?: string; ended_at?: string; duration_seconds: number; pause_seconds: number; status: string; created_at?: string; updated_at?: string; }
export interface StudySessionCreate { mode: FocusMode; goal?: string; related_task_id?: string; }
export interface StudySessionFinish { self_report?: string; self_report_tags?: string[]; }
export interface StudyDailyGoal { target_minutes: number; updated_at: string; }
export interface PersonalFileItem { id: string; name: string; category?: string; size_label?: string; updated_at?: string; source?: string; is_favorite?: boolean; }
export interface PersonalFileCreate { name: string; category: string; source: string; size_label: string; }
export interface FavoriteItem { id: string; title: string; type?: string; subtitle?: string; saved_at?: string; source_route?: string; }

export interface NoticeIngestRequest { content: string; source_name: string; published_at: string; }
export interface ExtractRequest { content: string; }
export interface NoticeExtractTaskItem { title: string; task: string; actionable: boolean; deadline?: string; source_name?: string; confidence: number; importance: string; source_text: string; }
export interface MultiNoticeExtractResponse { tasks: NoticeExtractTaskItem[]; split_reason: string; needs_user_confirmation: boolean; }
export interface ExtractResult { title: string; source: string; deadline: string; tasks: string[]; confidence: number; error?: string; saved?: boolean; }
export interface TaskCreateRequest { title: string; description?: string; deadline?: string; source_name?: string; source_text?: string; priority?: string; }
export interface LocalCapturedNotice { id: string; title: string; content: string; source: string; source_type: string; time: string; fingerprint: string; captured_at: number; }
export interface UniversityItem { id: string; name: string; short_name?: string; province?: string; city?: string; academic_provider: string; forum_enabled: boolean; is_demo: boolean; }
export interface UniversitySelectionResponse { university_id?: string; university?: UniversityItem; }
export interface UniversitySelectionRequest { university_id: string; }
export interface CommunityPostItem { id: string; title: string; content: string; category: string; author_name: string; is_anonymous: boolean; like_count: number; comment_count: number; favorite_count: number; created_at: string; images?: string[]; extra?: CommunityPostExtra; liked?: boolean; favorited?: boolean; is_owner?: boolean; view_count?: number; status?: string; author_id?: string; }
export interface CommunityPostExtra {
  location?: string;
  topic_tag?: string;
  tags?: string[];
  allow_comments?: boolean;
  headcount?: number;
  deadline?: string;
  price?: number;
  kind?: string;
  contact?: string;
  contact_visibility?: string;
}
export interface CommunityComment { id: string; post_id: string; author_id: string; author_name: string; parent_comment_id?: string; content: string; is_anonymous: boolean; status: string; created_at: string; }
export interface CommunityCommentCreatePayload { content: string; is_anonymous: boolean; parent_comment_id: string; }
export interface CommunityReportCreatePayload { target_type: string; target_id: string; reason: string; details?: string; }
export interface CommunityPostPayload {
  title: string;
  content: string;
  category: string;
  post_type?: string;
  sub_category?: string;
  images: string[];
  is_anonymous: boolean;
  extra?: CommunityPostExtra;
}
export interface UploadImageResult { url: string; filename: string; size: number; }
export interface CommunityPostUpdatePayload {
  title?: string;
  content?: string;
  category?: string;
  images?: string[];
  is_anonymous?: boolean;
  extra?: CommunityPostExtra;
}
export interface AcademicStatusItem { status: string; provider: string; last_synced_at?: string; external_student_id?: string; }
