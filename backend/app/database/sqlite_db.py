"""SQLite 数据库初始化(基于 sqlite3，无 ORM 依赖)。

为后续迁移 PostgreSQL 保留空间：所有 SQL 使用标准方言，
切换时仅需替换连接层。

设计要点：
- 文件模式：每请求新连接 + WAL，避免多线程读阻塞。
- 内存模式：使用单条共享连接(`check_same_thread=False`)，
  因为 `:memory:` 库的 schema 仅存在于打开它的连接中。
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.core.config import Settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source_department TEXT,
    source_type TEXT,
    original_filename TEXT,
    content_hash TEXT UNIQUE NOT NULL,
    content_text TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    published_at TEXT,
    updated_at TEXT,
    effective_from TEXT,
    effective_to TEXT,
    version TEXT,
    applicable_students TEXT,
    is_official INTEGER DEFAULT 0,
    is_expired INTEGER DEFAULT 0,
    is_demo INTEGER DEFAULT 0,
    file_size INTEGER,
    file_ext TEXT,
    imported_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_documents_title ON documents(title);
-- idx_documents_is_demo 在 _migrate() 中创建:旧库可能缺 is_demo 列,
-- 在 ALTER TABLE 之前创建索引会触发 "no such column: is_demo"。

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    section TEXT,
    position INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY(document_id) REFERENCES documents(document_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    last_message_at TEXT
);

CREATE TABLE IF NOT EXISTS app_meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id TEXT PRIMARY KEY,
    actor_user_id TEXT,
    actor_name_snapshot TEXT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    description TEXT NOT NULL,
    result TEXT NOT NULL DEFAULT 'success',
    request_id TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_actor ON audit_logs(actor_user_id);
"""


# 多角色协同平台 schema —— 教师/课程/班级/学生/任务/提交。
# 所有新表均使用 IF NOT EXISTS，保证幂等。
# 不破坏既有 documents/chunks/conversations/app_meta 表。
MULTI_ROLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    display_name TEXT,
    student_number TEXT,
    teacher_number TEXT,
    college TEXT,
    major TEXT,
    grade TEXT,
    avatar_url TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
-- 依赖可迁移列的 student/teacher number 索引在 _migrate() 中创建。

CREATE TABLE IF NOT EXISTS refresh_tokens (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_hash ON refresh_tokens(token_hash);

CREATE TABLE IF NOT EXISTS courses (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    semester TEXT,
    description TEXT,
    teacher_id TEXT,
    owner_user_id TEXT,
    remote_teacher_name TEXT,
    remote_class_id TEXT,
    remote_cpi TEXT,
    remote_school_name TEXT,
    remote_class_name TEXT,
    remote_student_count INTEGER,
    cover_url TEXT,
    starts_at TEXT,
    ends_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    provider TEXT,
    external_id TEXT,
    source_url TEXT,
    last_synced_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(teacher_id) REFERENCES users(id) ON DELETE RESTRICT,
    FOREIGN KEY(owner_user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_courses_teacher_id ON courses(teacher_id);
CREATE INDEX IF NOT EXISTS idx_courses_status ON courses(status);
-- idx_courses_external_id 和 idx_courses_owner_user_id 在 _migrate() 中创建，兼容旧 courses 表。

CREATE TABLE IF NOT EXISTS class_groups (
    id TEXT PRIMARY KEY,
    course_id TEXT NOT NULL,
    name TEXT NOT NULL,
    class_code TEXT,
    invite_code TEXT NOT NULL UNIQUE,
    description TEXT,
    capacity INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_class_groups_course_id ON class_groups(course_id);

CREATE TABLE IF NOT EXISTS enrollments (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    member_role TEXT NOT NULL DEFAULT 'student',
    status TEXT NOT NULL DEFAULT 'active',
    joined_at TEXT NOT NULL,
    UNIQUE(class_group_id, user_id),
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_enrollments_class_group_id ON enrollments(class_group_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_user_id ON enrollments(user_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_status ON enrollments(status);

CREATE TABLE IF NOT EXISTS announcements (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    require_read INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_announcements_class_group_id ON announcements(class_group_id);
CREATE INDEX IF NOT EXISTS idx_announcements_status ON announcements(status);
CREATE INDEX IF NOT EXISTS idx_announcements_published_at ON announcements(published_at);

CREATE TABLE IF NOT EXISTS announcement_read_receipts (
    announcement_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    read_at TEXT NOT NULL,
    PRIMARY KEY (announcement_id, student_id),
    FOREIGN KEY(announcement_id) REFERENCES announcements(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_read_receipts_announcement_id ON announcement_read_receipts(announcement_id);
CREATE INDEX IF NOT EXISTS idx_read_receipts_student_id ON announcement_read_receipts(student_id);

CREATE TABLE IF NOT EXISTS assignments (
    id TEXT PRIMARY KEY,
    class_group_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    deadline TEXT,
    submission_types TEXT,
    max_score REAL,
    allow_resubmit INTEGER DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(class_group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_assignments_class_group_id ON assignments(class_group_id);
CREATE INDEX IF NOT EXISTS idx_assignments_status ON assignments(status);
CREATE INDEX IF NOT EXISTS idx_assignments_deadline ON assignments(deadline);

CREATE TABLE IF NOT EXISTS submissions (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    student_id TEXT NOT NULL,
    text_content TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    submitted_at TEXT,
    updated_at TEXT NOT NULL,
    score REAL,
    teacher_comment TEXT,
    UNIQUE(assignment_id, student_id),
    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY(student_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id ON submissions(assignment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student_id ON submissions(student_id);
CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);

CREATE TABLE IF NOT EXISTS submission_attachments (
    id TEXT PRIMARY KEY,
    submission_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(submission_id) REFERENCES submissions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_submission_attachments_submission_id ON submission_attachments(submission_id);

CREATE TABLE IF NOT EXISTS assignment_attachments (
    id TEXT PRIMARY KEY,
    assignment_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER,
    storage_path TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(assignment_id) REFERENCES assignments(id) ON DELETE CASCADE,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_assignment_attachments_assignment_id ON assignment_attachments(assignment_id);
"""


# 个人待办 schema —— 学生从通知抽取生成的个人任务。
# 与 assignments(教师发布的班级作业)严格分离:
# - user_id 绑定 JWT 用户,禁止跨用户读取
# - source_text 保留原通知文本,确保可追溯
# - deleted_at 软删除字段,避免立即物理删除
PERSONAL_TASK_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS personal_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    target_students TEXT,
    deadline TEXT,
    materials TEXT,
    submission_method TEXT,
    location TEXT,
    source_name TEXT,
    source_text TEXT,
    source_notice_id TEXT,
    priority TEXT NOT NULL DEFAULT 'medium',
    importance TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'pending',
    reminder_minutes INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    deleted_at TEXT,
    source TEXT,
    external_id TEXT,
    course_id TEXT,
    source_url TEXT,
    last_synced_at TEXT,
    -- 学习通等外部平台回传的成绩事实(均为可空，未采集到时保持 NULL)。
    remote_submitted_at TEXT,
    score REAL,
    score_max REAL,
    graded_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, source_notice_id),
    UNIQUE(user_id, source, external_id)
);

"""


# 学习陪伴 schema —— 学习会话 / 休息记录。
# 所有记录绑定 user_id(JWT 用户隔离)。状态机由仓库层与路由层共同校验。
STUDY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS study_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'focus',
    experience_mode TEXT NOT NULL DEFAULT 'QUIET',
    goal TEXT,
    related_task_id TEXT,
    started_at TEXT NOT NULL,
    paused_at TEXT,
    ended_at TEXT,
    planned_duration_seconds INTEGER NOT NULL DEFAULT 0,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    pause_seconds INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    self_report TEXT,
    self_report_tags TEXT,
    expression_signal TEXT,
    behavior_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_id ON study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_status ON study_sessions(status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_status ON study_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_started_at ON study_sessions(started_at);

CREATE TABLE IF NOT EXISTS study_checkins (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    date_key TEXT NOT NULL,
    scene TEXT NOT NULL DEFAULT 'rain',
    mood TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, date_key)
);
CREATE INDEX IF NOT EXISTS idx_study_checkins_user_date ON study_checkins(user_id, date_key);

CREATE TABLE IF NOT EXISTS study_breaks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES study_sessions(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_study_breaks_session_id ON study_breaks(session_id);

CREATE TABLE IF NOT EXISTS study_goals (
    user_id TEXT PRIMARY KEY,
    target_minutes INTEGER NOT NULL CHECK(target_minutes BETWEEN 15 AND 480),
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""


# 个人中心 schema —— 用户私有文件与跨模块收藏。
# - user_id 绑定 JWT 用户,禁止跨用户读取
# - favorites 使用 (user_id, id) 复合主键,允许不同用户收藏同一个对象
PERSONAL_HUB_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS personal_files (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT,
    size_label TEXT,
    updated_at TEXT,
    source TEXT,
    is_favorite INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_personal_files_user_id ON personal_files(user_id);

CREATE TABLE IF NOT EXISTS favorites (
    user_id TEXT NOT NULL,
    id TEXT NOT NULL,
    title TEXT NOT NULL,
    type TEXT,
    subtitle TEXT,
    saved_at TEXT,
    source_route TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, id),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_favorites_user_id ON favorites(user_id);
"""

HOME_BANNER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS home_banners (
    id TEXT PRIMARY KEY,
    eyebrow TEXT NOT NULL,
    title TEXT NOT NULL,
    subtitle TEXT NOT NULL,
    cta_label TEXT NOT NULL,
    image_url TEXT NOT NULL,
    action_key TEXT NOT NULL,
    theme_key TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    starts_at TEXT,
    ends_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_home_banners_public
    ON home_banners(status, sort_order, starts_at, ends_at);
"""

CHAOXING_CREDENTIALS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chaoxing_credentials (
    user_id TEXT PRIMARY KEY,
    encrypted_cookies TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

# 学习通考试/测验事实表 —— 承载考试时间与得分，供世界模型 ACADEMIC/WORLD 投影消费。
# 与 course_content_items 中的 exam_candidate 条目互补: 后者用于前端内容展示，
# 本表用于结构化成绩与考试暴露度计算，并作为 exam_discovered 事件的证据表。
CHAOXING_ASSESSMENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chaoxing_exams (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    exam_at TEXT,
    score REAL,
    score_max REAL,
    status TEXT NOT NULL DEFAULT 'discovered',
    source_url TEXT,
    first_seen_at TEXT NOT NULL,
    last_synced_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_chaoxing_exams_user
    ON chaoxing_exams(user_id);
CREATE INDEX IF NOT EXISTS idx_chaoxing_exams_course
    ON chaoxing_exams(user_id, course_id);
"""

# 课程知识图谱 —— 学习通课程图谱页发布的"知识点体系 + 掌握率"。
# 这是外部数据源观测(课程/学校发布的知识点 + 平台统计)，不是平台自造推断，
# 因此与已删除的 C 语言学习系统 knowledge_components 无关，命名也刻意避开旧术语。
CHAOXING_KNOWLEDGE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chaoxing_knowledge_graphs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT,
    external_course_id TEXT,
    knowledge_point_count INTEGER NOT NULL DEFAULT 0,
    own_mastery_rate REAL,
    class_mastery_rate REAL,
    own_completion_rate REAL,
    class_completion_rate REAL,
    first_seen_at TEXT NOT NULL,
    synced_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, course_id)
);
CREATE INDEX IF NOT EXISTS idx_chaoxing_knowledge_graphs_user
    ON chaoxing_knowledge_graphs(user_id);

CREATE TABLE IF NOT EXISTS chaoxing_knowledge_points (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    level INTEGER,
    tags TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    first_seen_at TEXT NOT NULL,
    last_synced_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, external_id)
);
CREATE INDEX IF NOT EXISTS idx_chaoxing_knowledge_points_user
    ON chaoxing_knowledge_points(user_id, course_id);
"""

NOTICES_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS notices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    course_id TEXT,
    title TEXT NOT NULL,
    content TEXT,
    published_at TEXT,
    source_url TEXT,
    last_synced_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_notices_user_id ON notices(user_id);
CREATE INDEX IF NOT EXISTS idx_notices_published_at ON notices(published_at);

CREATE TABLE IF NOT EXISTS notice_ingest_results (
    user_id TEXT NOT NULL,
    client_fingerprint TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY(user_id, client_fingerprint),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notice_ingest_claims (
    user_id TEXT NOT NULL,
    client_fingerprint TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    PRIMARY KEY(user_id, client_fingerprint),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notice_ai_cache (
    cache_key TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS course_content_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'chaoxing',
    external_id TEXT NOT NULL,
    parent_external_id TEXT,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    author_name TEXT,
    position INTEGER NOT NULL DEFAULT 0,
    depth INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'unknown',
    starts_at TEXT,
    deadline TEXT,
    published_at TEXT,
    mime_type TEXT,
    file_size INTEGER,
    remote_object_id TEXT,
    source_url TEXT,
    metadata_json TEXT,
    is_stale INTEGER NOT NULL DEFAULT 0,
    last_synced_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE(user_id, provider, course_id, kind, external_id)
);
CREATE INDEX IF NOT EXISTS idx_course_content_lookup
ON course_content_items(user_id, course_id, kind, parent_external_id, position);

CREATE TABLE IF NOT EXISTS course_sync_sections (
    user_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    section TEXT NOT NULL,
    status TEXT NOT NULL,
    item_count INTEGER NOT NULL DEFAULT 0,
    -- last_synced_at 是"最近一次尝试"时间(失败也会刷新)；
    -- last_success_at 只在 status 为 complete/partial 时前进，用来回答
    -- "最近一次成功同步到数据是什么时候"。两者必须分开，否则一次失败就会
    -- 抹掉真实的成功时间，把 never_synced 误报成 empty。
    last_synced_at TEXT NOT NULL,
    last_success_at TEXT,
    error_code TEXT,
    error_message TEXT,
    PRIMARY KEY(user_id, course_id, section),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_course_sync_sections_course
ON course_sync_sections(user_id, course_id);

CREATE TABLE IF NOT EXISTS course_resource_cache (
    item_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    course_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    mime_type TEXT,
    file_size INTEGER NOT NULL,
    cached_at TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    expires_at TEXT,
    PRIMARY KEY(item_id, user_id),
    FOREIGN KEY(item_id) REFERENCES course_content_items(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(course_id) REFERENCES courses(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_course_resource_cache_access
ON course_resource_cache(last_accessed_at);
"""

UNIVERSITY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS universities (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    short_name TEXT,
    province TEXT,
    city TEXT,
    country TEXT NOT NULL DEFAULT 'China',
    level TEXT,
    school_code TEXT,
    logo_url TEXT,
    official_domain TEXT,
    official_website TEXT,
    academic_system_type TEXT NOT NULL DEFAULT 'unsupported',
    academic_system_url TEXT,
    academic_provider TEXT NOT NULL DEFAULT 'unsupported',
    forum_enabled INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    is_demo INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_universities_status_name ON universities(status, name);
CREATE INDEX IF NOT EXISTS idx_universities_location ON universities(province, city);

"""

COMMUNITY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS forum_posts (
    id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    images_json TEXT NOT NULL DEFAULT '[]',
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'published',
    like_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    favorite_count INTEGER NOT NULL DEFAULT 0,
    extra_json TEXT NOT NULL DEFAULT '{}',
    view_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forum_posts_feed
ON forum_posts(university_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_forum_posts_category
ON forum_posts(university_id, status, category, created_at DESC);

CREATE TABLE IF NOT EXISTS forum_comments (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL,
    university_id TEXT NOT NULL,
    author_id TEXT NOT NULL,
    parent_comment_id TEXT,
    content TEXT NOT NULL,
    is_anonymous INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'published',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(parent_comment_id) REFERENCES forum_comments(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forum_comments_post ON forum_comments(post_id, status, created_at);

CREATE TABLE IF NOT EXISTS forum_likes (
    post_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(post_id, user_id),
    FOREIGN KEY(post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS forum_favorites (
    post_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(post_id, user_id),
    FOREIGN KEY(post_id) REFERENCES forum_posts(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS forum_reports (
    id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL,
    reporter_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT,
    FOREIGN KEY(reporter_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_forum_reports_status ON forum_reports(status, created_at);
"""

ACADEMIC_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS academic_bindings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    university_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    external_student_id TEXT,
    status TEXT NOT NULL,
    last_synced_at TEXT,
    credential_ref TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_academic_bindings_university ON academic_bindings(university_id, provider);
"""


# CampusMate EduConnector schema —— 高校教务系统统一连接层。
# 架构：universities 1:N edu_systems（一所学校可有多个教务系统）。
# 严禁编造教务系统 URL：未确认数据必须为 null，url_status 必须为 not_discovered。
EDU_CONNECTOR_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS edu_system_configs (
    id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL DEFAULT 'unknown',
    system_type TEXT NOT NULL DEFAULT 'unknown',
    academic_system_url TEXT,
    academic_system_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    undergrad_system_url TEXT,
    undergrad_system_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    postgrad_system_url TEXT,
    postgrad_system_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    sso_url TEXT,
    sso_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    cas_url TEXT,
    cas_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    webvpn_url TEXT,
    webvpn_url_status TEXT NOT NULL DEFAULT 'not_discovered',
    login_method TEXT NOT NULL DEFAULT 'unknown',
    captcha_type TEXT NOT NULL DEFAULT 'unknown',
    requires_campus_network INTEGER,
    supported_features TEXT NOT NULL DEFAULT '[]',
    school_code TEXT,
    notes TEXT,
    data_source TEXT NOT NULL DEFAULT 'unknown',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edu_system_configs_provider ON edu_system_configs(provider);

CREATE TABLE IF NOT EXISTS edu_systems (
    id TEXT PRIMARY KEY,
    university_id TEXT NOT NULL,
    school_code TEXT,
    system_key TEXT NOT NULL,
    name TEXT,
    system_type TEXT NOT NULL DEFAULT 'unknown',
    provider TEXT NOT NULL DEFAULT 'unknown',
    provider_version TEXT,
    base_url TEXT,
    login_url TEXT,
    sso_url TEXT,
    vpn_url TEXT,
    auth_type TEXT NOT NULL DEFAULT 'unknown',
    login_execution_mode TEXT NOT NULL DEFAULT 'unsupported',
    captcha_type TEXT NOT NULL DEFAULT 'unknown',
    requires_campus_network INTEGER NOT NULL DEFAULT 0,
    requires_vpn INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    verification_status TEXT NOT NULL DEFAULT 'unverified',
    supported_features TEXT NOT NULL DEFAULT '[]',
    adapter_config TEXT NOT NULL DEFAULT '{}',
    last_verified_at TEXT,
    source TEXT NOT NULL DEFAULT 'unknown',
    notes TEXT,
    is_mock INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE CASCADE
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_systems_uni_key ON edu_systems(university_id, system_key);
CREATE INDEX IF NOT EXISTS idx_edu_systems_provider ON edu_systems(provider);
CREATE INDEX IF NOT EXISTS idx_edu_systems_university ON edu_systems(university_id);

CREATE TABLE IF NOT EXISTS edu_bindings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT,
    university_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    system_type TEXT NOT NULL DEFAULT 'undergrad',
    external_student_id TEXT,
    external_student_name TEXT,
    connection_status TEXT NOT NULL DEFAULT 'unbound',
    session_type TEXT,
    credential_ref TEXT,
    last_authenticated_at TEXT,
    session_expires_at TEXT,
    last_synced_at TEXT,
    last_sync_status TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE CASCADE,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_bindings_user_system ON edu_bindings(user_id, edu_system_id);
CREATE INDEX IF NOT EXISTS idx_edu_bindings_university ON edu_bindings(university_id, provider);
CREATE INDEX IF NOT EXISTS idx_edu_bindings_status ON edu_bindings(connection_status);

CREATE TABLE IF NOT EXISTS edu_connections (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT NOT NULL,
    university_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'idle',
    provider TEXT NOT NULL DEFAULT 'unknown',
    login_execution_mode TEXT NOT NULL DEFAULT 'unsupported',
    portal_url TEXT,
    credential_ref TEXT,
    external_student_id TEXT,
    external_student_name TEXT,
    error_code TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE CASCADE,
    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_edu_connections_user ON edu_connections(user_id, state);

CREATE TABLE IF NOT EXISTS edu_sync_records (
    id TEXT PRIMARY KEY,
    binding_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    sync_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    items_count INTEGER NOT NULL DEFAULT 0,
    adapter TEXT,
    adapter_version TEXT,
    error_code TEXT,
    error_message TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(binding_id) REFERENCES edu_bindings(id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edu_sync_records_binding ON edu_sync_records(binding_id, sync_type);
CREATE INDEX IF NOT EXISTS idx_edu_sync_records_user ON edu_sync_records(user_id, started_at);
"""


# CampusMate EduConnector 同步数据持久化 schema。
# 把 Adapter 归一化后的 EduSchedule / EduGrade 落库，供三端真实展示。
# 幂等同步：基于 (user_id, edu_system_id, semester, course_code, weekday, start_section, weeks) 唯一键。
# 软删除：stale 行不物理删除，标记 is_stale=1 + last_seen_at，保留历史。
EDU_DATA_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS edu_courses (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT,
    university_id TEXT NOT NULL,
    semester TEXT,
    course_code TEXT,
    course_name TEXT NOT NULL,
    provider TEXT,
    source TEXT NOT NULL DEFAULT 'edu_connector',
    external_course_id TEXT,
    source_hash TEXT,
    last_seen_at TEXT NOT NULL,
    sync_batch_id TEXT,
    is_stale INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_courses_unique ON edu_courses(
    user_id, edu_system_id, semester, course_code
) WHERE course_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_edu_courses_user_semester ON edu_courses(user_id, semester);
CREATE INDEX IF NOT EXISTS idx_edu_courses_stale ON edu_courses(is_stale);

CREATE TABLE IF NOT EXISTS edu_schedule_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT,
    university_id TEXT NOT NULL,
    semester TEXT,
    course_code TEXT,
    course_name TEXT NOT NULL,
    teacher TEXT,
    teachers TEXT,
    location TEXT,
    campus TEXT,
    building TEXT,
    classroom TEXT,
    weekday INTEGER,
    start_section INTEGER,
    end_section INTEGER,
    start_time TEXT,
    end_time TEXT,
    weeks TEXT,
    week_text TEXT,
    credit REAL,
    course_nature TEXT,
    course_category TEXT,
    course_type TEXT,
    teaching_class TEXT,
    class_name TEXT,
    college TEXT,
    department TEXT,
    assessment_method TEXT,
    exam_type TEXT,
    total_hours REAL,
    theory_hours REAL,
    practice_hours REAL,
    language TEXT,
    note TEXT,
    semester_id TEXT,
    extra_info TEXT,
    provider TEXT,
    source TEXT NOT NULL DEFAULT 'edu_connector',
    source_hash TEXT,
    last_seen_at TEXT NOT NULL,
    sync_batch_id TEXT,
    is_stale INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_schedule_items_unique ON edu_schedule_items(
    user_id, edu_system_id, semester, course_code, weekday, start_section, weeks
) WHERE course_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_edu_schedule_items_user_semester ON edu_schedule_items(user_id, semester);
CREATE INDEX IF NOT EXISTS idx_edu_schedule_items_weekday ON edu_schedule_items(user_id, semester, weekday);
CREATE INDEX IF NOT EXISTS idx_edu_schedule_items_stale ON edu_schedule_items(is_stale);

CREATE TABLE IF NOT EXISTS edu_grades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT,
    university_id TEXT NOT NULL,
    semester TEXT,
    course_code TEXT,
    course_name TEXT NOT NULL,
    credit REAL,
    score TEXT,
    grade_point REAL,
    category TEXT,
    status TEXT,
    provider TEXT,
    source TEXT NOT NULL DEFAULT 'edu_connector',
    source_hash TEXT,
    last_seen_at TEXT NOT NULL,
    sync_batch_id TEXT,
    is_stale INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_grades_unique ON edu_grades(
    user_id, edu_system_id, semester, course_code
) WHERE course_code IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_edu_grades_user_semester ON edu_grades(user_id, semester);
CREATE INDEX IF NOT EXISTS idx_edu_grades_stale ON edu_grades(is_stale);

CREATE TABLE IF NOT EXISTS edu_exam_items (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    edu_system_id TEXT,
    university_id TEXT NOT NULL,
    semester TEXT,
    course_code TEXT,
    course_name TEXT NOT NULL,
    exam_type TEXT,
    location TEXT,
    seat TEXT,
    starts_at TEXT,
    ends_at TEXT,
    notes TEXT,
    provider TEXT,
    source TEXT NOT NULL DEFAULT 'edu_connector',
    source_hash TEXT,
    last_seen_at TEXT NOT NULL,
    sync_batch_id TEXT,
    is_stale INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(edu_system_id) REFERENCES edu_systems(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_exam_items_unique ON edu_exam_items(
    user_id, edu_system_id, semester, course_code, course_name, exam_type, starts_at
);
CREATE INDEX IF NOT EXISTS idx_edu_exam_items_user_semester ON edu_exam_items(user_id, semester);
CREATE INDEX IF NOT EXISTS idx_edu_exam_items_stale ON edu_exam_items(is_stale);
"""


# QR 扫码登录 + 可信设备 schema
# - qr_login_sessions: 二维码登录会话状态机
# - trusted_devices: 可信设备自动登录凭据
QR_AUTH_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS qr_login_sessions (
    id TEXT PRIMARY KEY,
    scan_token_hash TEXT NOT NULL,
    browser_token_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    user_id TEXT,
    device_id TEXT,
    browser_name TEXT,
    os_name TEXT,
    device_label TEXT,
    user_agent TEXT,
    trust_device INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    scanned_at TEXT,
    confirmed_at TEXT,
    consumed_at TEXT,
    cancelled_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_qr_sessions_status ON qr_login_sessions(status);
CREATE INDEX IF NOT EXISTS idx_qr_sessions_user ON qr_login_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_qr_sessions_expires ON qr_login_sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_qr_sessions_device ON qr_login_sessions(device_id);

CREATE TABLE IF NOT EXISTS trusted_devices (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    device_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    device_name TEXT,
    browser_name TEXT,
    os_name TEXT,
    user_agent TEXT,
    created_at TEXT NOT NULL,
    last_used_at TEXT,
    expires_at TEXT NOT NULL,
    revoked_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_user ON trusted_devices(user_id);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_token ON trusted_devices(token_hash);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_device ON trusted_devices(device_id);
CREATE INDEX IF NOT EXISTS idx_trusted_devices_expires ON trusted_devices(expires_at);
"""


EDU_SESSION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS edu_sessions (
    connection_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    envelope_version INTEGER NOT NULL,
    key_id TEXT NOT NULL,
    nonce BLOB NOT NULL,
    ciphertext BLOB NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_edu_sessions_user ON edu_sessions(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_edu_sessions_expires ON edu_sessions(expires_at);
"""

LEARNER_EVENT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learner_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL,
    course_id TEXT,
    subject_type TEXT,
    subject_id TEXT,
    external_ref TEXT,
    outcome TEXT,
    duration_seconds INTEGER CHECK(duration_seconds IS NULL OR duration_seconds >= 0),
    evidence_reference_json TEXT NOT NULL,
    data_quality TEXT NOT NULL,
    consent_scope TEXT NOT NULL,
    source_version TEXT,
    dedupe_key TEXT NOT NULL,
    payload_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_learner_events_user_time ON learner_events(user_id, occurred_at);
CREATE INDEX IF NOT EXISTS idx_learner_events_user_source_type ON learner_events(user_id, source, event_type);
CREATE INDEX IF NOT EXISTS idx_learner_events_user_course ON learner_events(user_id, course_id);
CREATE INDEX IF NOT EXISTS idx_learner_events_user_subject ON learner_events(user_id, subject_type, subject_id);
"""

LEARNER_STATE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learner_state_projection_runs (
    run_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    as_of TEXT NOT NULL,
    computed_at TEXT NOT NULL,
    estimator_version TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    trigger TEXT NOT NULL,
    projection_kind TEXT NOT NULL DEFAULT 'CORE',
    projection_scope TEXT NOT NULL DEFAULT '__user__',
    is_current INTEGER NOT NULL DEFAULT 0 CHECK(is_current IN (0, 1)),
    warnings_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learner_state_runs_user_time
    ON learner_state_projection_runs(user_id, computed_at DESC);
CREATE TABLE IF NOT EXISTS learner_state_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    scope_type TEXT NOT NULL,
    scope_id TEXT NOT NULL,
    state_type TEXT NOT NULL,
    value_json TEXT NOT NULL,
    confidence REAL NOT NULL CHECK(confidence >= 0 AND confidence <= 1),
    data_quality TEXT NOT NULL,
    observed_from TEXT,
    observed_through TEXT,
    valid_until TEXT,
    computed_at TEXT NOT NULL,
    UNIQUE(run_id, scope_type, scope_id, state_type),
    FOREIGN KEY(run_id) REFERENCES learner_state_projection_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learner_state_snapshots_run
    ON learner_state_snapshots(run_id, scope_type, scope_id, state_type);
CREATE INDEX IF NOT EXISTS idx_learner_state_snapshots_scope
    ON learner_state_snapshots(scope_type, scope_id, state_type);

CREATE TABLE IF NOT EXISTS learner_state_evidence (
    evidence_id TEXT PRIMARY KEY,
    snapshot_id TEXT NOT NULL,
    evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('EVENT', 'SOURCE_ROW', 'SYNC_STATUS')),
    event_id TEXT,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('SUPPORTS', 'LIMITS', 'INVALIDATES')),
    quality TEXT NOT NULL,
    explanation_code TEXT NOT NULL DEFAULT 'state_observed',
    FOREIGN KEY(snapshot_id) REFERENCES learner_state_snapshots(snapshot_id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES learner_events(event_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learner_state_evidence_snapshot
    ON learner_state_evidence(snapshot_id, evidence_id);
CREATE INDEX IF NOT EXISTS idx_learner_state_evidence_event
    ON learner_state_evidence(event_id);
"""

LEARNING_PLAN_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS learning_plan_runs (
    run_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    planner_version TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    as_of TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    available_minutes INTEGER NOT NULL CHECK(available_minutes > 0),
    allocated_minutes INTEGER NOT NULL DEFAULT 0 CHECK(allocated_minutes >= 0),
    course_scope TEXT,
    goal_id TEXT,
    window_start TEXT,
    window_end TEXT,
    warning_codes_json TEXT NOT NULL DEFAULT '[]',
    idempotency_key TEXT,
    core_run_id TEXT,
    core_input_digest TEXT,
    knowledge_bindings_json TEXT NOT NULL DEFAULT '{}',
    task_binding_digest TEXT,
    task_bindings_json TEXT NOT NULL DEFAULT '{}',
    input_truncated INTEGER NOT NULL DEFAULT 0,
    core_quality TEXT NOT NULL DEFAULT 'verified',
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_runs_user_created
    ON learning_plan_runs(user_id, created_at DESC, run_id DESC);
CREATE INDEX IF NOT EXISTS idx_learning_plan_runs_digest
    ON learning_plan_runs(user_id, planner_version, input_digest, valid_until);
CREATE INDEX IF NOT EXISTS idx_learning_plan_runs_goal
    ON learning_plan_runs(user_id, goal_id, created_at DESC);

CREATE TABLE IF NOT EXISTS learning_plans (
    plan_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PROPOSED','ACCEPTED','REJECTED','EXECUTED','PARTIALLY_EXECUTED','UNDONE','EXPIRED')),
    llm_summary TEXT,
    supersedes_plan_id TEXT,
    superseded_by_plan_id TEXT,
    stale_reason TEXT,
    replan_key TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES learning_plan_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learning_plans_user_created
    ON learning_plans(user_id, created_at DESC, plan_id DESC);

CREATE TABLE IF NOT EXISTS learning_plan_items (
    item_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    item_type TEXT NOT NULL,
    course_id TEXT,
    task_id TEXT,
    estimated_minutes INTEGER NOT NULL CHECK(estimated_minutes > 0),
    priority_score REAL NOT NULL,
    priority_components_json TEXT NOT NULL,
    explanation_codes_json TEXT NOT NULL,
    execution_status TEXT NOT NULL DEFAULT 'PENDING' CHECK(execution_status IN ('PENDING','SUCCEEDED','FAILED','SKIPPED','UNDONE')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_items_plan_order
    ON learning_plan_items(plan_id, priority_score DESC, item_id ASC);

CREATE TABLE IF NOT EXISTS learning_plan_evidence (
    evidence_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    reference_id TEXT NOT NULL,
    relevance_score REAL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(item_id) REFERENCES learning_plan_items(item_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_evidence_item
    ON learning_plan_evidence(item_id, evidence_id);

CREATE TABLE IF NOT EXISTS learning_plan_decisions (
    decision_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('ACCEPT','REJECT')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_decisions_plan
    ON learning_plan_decisions(plan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS learning_plan_execution_actions (
    action_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING','SUCCEEDED','FAILED','UNDONE')),
    target_task_id TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    target_task_digest TEXT,
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(item_id) REFERENCES learning_plan_items(item_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(plan_id, item_id, action_type)
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_actions_plan
    ON learning_plan_execution_actions(plan_id, created_at, action_id);

CREATE TABLE IF NOT EXISTS learning_plan_feedback (
    feedback_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    feedback TEXT NOT NULL CHECK(feedback IN ('HELPFUL','NOT_HELPFUL','TOO_LONG','TOO_SHORT','WRONG_PRIORITY','ALREADY_DONE','MISSING_CONTEXT')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(plan_id, user_id, feedback)
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_feedback_plan ON learning_plan_feedback(plan_id, created_at);

CREATE TABLE IF NOT EXISTS learning_plan_evaluation_runs (
    evaluation_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    baseline_as_of TEXT NOT NULL,
    evaluated_as_of TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    warning_codes_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(plan_id, evaluator_version, input_digest)
);
CREATE INDEX IF NOT EXISTS idx_learning_plan_evaluations_plan ON learning_plan_evaluation_runs(plan_id, created_at DESC);
"""

MODEL_SHADOW_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS model_shadow_runs (
    shadow_run_id TEXT PRIMARY KEY,
    scope TEXT NOT NULL CHECK(scope IN ('ONLINE','OFFLINE')),
    user_id TEXT,
    request_id TEXT NOT NULL,
    capability_name TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    production_model_key TEXT NOT NULL,
    candidate_model_key TEXT NOT NULL,
    dataset_version TEXT,
    online_sample_version TEXT,
    prompt_version TEXT NOT NULL,
    input_digest TEXT NOT NULL,
    expected_output_digest TEXT,
    candidate_output_digest TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(scope, user_id, request_id, capability_name, capability_version)
);
CREATE INDEX IF NOT EXISTS idx_model_shadow_runs_user_created
    ON model_shadow_runs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_model_shadow_runs_capability
    ON model_shadow_runs(capability_name, capability_version, created_at DESC);

CREATE TABLE IF NOT EXISTS model_shadow_results (
    shadow_run_id TEXT PRIMARY KEY,
    schema_valid INTEGER NOT NULL,
    policy_valid INTEGER NOT NULL,
    abstained INTEGER NOT NULL,
    used_fallback INTEGER NOT NULL,
    failure_code TEXT,
    latency_ms INTEGER NOT NULL,
    resource_metrics_json TEXT NOT NULL DEFAULT '{}',
    evaluator_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    inference_source TEXT NOT NULL DEFAULT 'DETERMINISTIC_FALLBACK'
        CHECK(inference_source IN ('REAL_MODEL','FIXTURE','DETERMINISTIC_FALLBACK','LEGACY_UNVERIFIED','NOT_OBSERVED')),
    FOREIGN KEY(shadow_run_id) REFERENCES model_shadow_runs(shadow_run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS model_shadow_metric_records (
    metric_record_id TEXT PRIMARY KEY,
    shadow_run_id TEXT,
    scope TEXT NOT NULL CHECK(scope IN ('ONLINE','OFFLINE')),
    capability_name TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    metrics_digest TEXT NOT NULL,
    metrics_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(shadow_run_id) REFERENCES model_shadow_runs(shadow_run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_model_shadow_metrics_capability
    ON model_shadow_metric_records(capability_name, capability_version, created_at DESC);

CREATE TABLE IF NOT EXISTS model_promotion_decisions (
    decision_id TEXT PRIMARY KEY,
    model_key TEXT NOT NULL,
    model_version TEXT NOT NULL,
    capability_name TEXT NOT NULL,
    capability_version TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    evaluator_version TEXT NOT NULL,
    threshold_version TEXT NOT NULL,
    metrics_digest TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('SHADOW_ONLY','ELIGIBLE_FOR_CANARY','BLOCKED','REVOKED')),
    failed_gates_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_model_promotion_capability
    ON model_promotion_decisions(model_key, capability_name, created_at DESC);
"""


LEARNER_CONTROL_SCHEMA_SQL = """
-- Phase 6A: 学生状态纠正
CREATE TABLE IF NOT EXISTS learner_state_corrections (
    correction_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    projection_kind TEXT NOT NULL CHECK(projection_kind IN ('CORE','KNOWLEDGE')),
    projection_scope TEXT NOT NULL,
    scope_type TEXT NOT NULL CHECK(scope_type IN ('USER','COURSE','TASK','SOURCE','KNOWLEDGE_COMPONENT')),
    scope_id TEXT NOT NULL,
    state_type TEXT NOT NULL,
    target_snapshot_id TEXT NOT NULL,
    correction_type TEXT NOT NULL CHECK(correction_type IN (
        'MARK_INACCURATE','NOT_APPLICABLE','SOURCE_OUTDATED','ALREADY_RESOLVED','REQUEST_RECOMPUTE'
    )),
    reason_code TEXT NOT NULL CHECK(reason_code IN (
        'TASK_ALREADY_COMPLETED','DEADLINE_CHANGED','COURSE_NO_LONGER_ACTIVE',
        'KNOWLEDGE_ESTIMATE_TOO_HIGH','KNOWLEDGE_ESTIMATE_TOO_LOW',
        'EVIDENCE_NOT_RELEVANT','SOURCE_DATA_STALE','OTHER_CONTROLLED_REASON'
    )),
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE','REVOKED')),
    created_at TEXT NOT NULL,
    revoked_at TEXT,
    correction_version INTEGER NOT NULL DEFAULT 1,
    idempotency_key TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_learner_corrections_user
    ON learner_state_corrections(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learner_corrections_snapshot
    ON learner_state_corrections(user_id, target_snapshot_id);

-- Phase 6A: 数据源控制
CREATE TABLE IF NOT EXISTS learner_data_source_controls (
    source_key TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ENABLED' CHECK(status IN (
        'ENABLED','PAUSED','DISCONNECTED','DELETE_REQUESTED'
    )),
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    PRIMARY KEY(source_key, user_id)
);

-- Phase 6A: 世界模型删除请求
CREATE TABLE IF NOT EXISTS learner_model_delete_requests (
    request_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    scope TEXT NOT NULL CHECK(scope IN (
        'STATE_ONLY','EVENTS_AND_STATE','KNOWLEDGE_ONLY','PLANS_ONLY',
        'MODEL_SHADOW_ONLY','ALL_LEARNER_MODEL_DATA'
    )),
    status TEXT NOT NULL DEFAULT 'COMPLETED' CHECK(status IN ('COMPLETED','IN_PROGRESS','FAILED')),
    before_counts_json TEXT NOT NULL DEFAULT '{}',
    after_counts_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    completed_at TEXT,
    idempotency_key TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learner_delete_requests_user
    ON learner_model_delete_requests(user_id, created_at DESC);

-- Phase 6A: 产品事件（固定枚举，不记录正文/标题/源码/凭据）
CREATE TABLE IF NOT EXISTS learner_product_events (
    event_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_learner_product_events_user
    ON learner_product_events(user_id, created_at DESC);
"""


# CampusAgentRuntime schema —— jobs/runs/steps/events/traces/artifacts(§5.6-§5.9、§7.1)。
# 所有迁移均为 additive + idempotent(CREATE TABLE IF NOT EXISTS)。
# trace 表只保存摘要、hash、延迟、路由与错误,不保存完整 prompt、隐藏推理或敏感上下文。
AGENT_RUNTIME_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS agent_jobs (
    job_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    job_kind TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    idempotency_key TEXT,
    input_ref_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_user ON agent_jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_jobs_kind ON agent_jobs(job_kind, status);

CREATE TABLE IF NOT EXISTS agent_runs (
    run_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'QUEUED',
    phase TEXT NOT NULL DEFAULT 'IDLE',
    risk_level TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_code TEXT,
    error_message TEXT,
    request_id TEXT,
    idempotency_key TEXT,
    retry_of TEXT,
    -- v2 持久化队列字段: 处理器身份、尝试次数、租约与恢复点。
    handler_code TEXT,
    handler_version TEXT,
    attempt_no INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    heartbeat_at TEXT,
    checkpoint_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(job_id) REFERENCES agent_jobs(job_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_runs_job ON agent_runs(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_user_status ON agent_runs(user_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status_phase ON agent_runs(status, phase);

CREATE TABLE IF NOT EXISTS agent_idempotency_claims (
    scope TEXT NOT NULL,
    user_id TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (scope, user_id, idempotency_key),
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_idem_claims_resource
    ON agent_idempotency_claims(resource_id);

CREATE TABLE IF NOT EXISTS agent_run_controls (
    command_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    resulting_status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(run_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_agent_run_controls_run ON agent_run_controls(run_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_run_steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    role TEXT NOT NULL,
    phase TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    summary TEXT,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_agent_run_steps_run ON agent_run_steps(run_id, sequence);

CREATE TABLE IF NOT EXISTS agent_context_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    run_id TEXT,
    user_id TEXT NOT NULL,
    scope_json TEXT NOT NULL DEFAULT '{}',
    facts_json TEXT NOT NULL DEFAULT '{}',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    source_digest TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    valid_until TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_context_snapshots_run ON agent_context_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_context_snapshots_user ON agent_context_snapshots(user_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS agent_tool_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT,
    tool_name TEXT NOT NULL,
    idempotency_key TEXT,
    request_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    result_digest TEXT,
    error_code TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, idempotency_key, request_hash)
);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_run ON agent_tool_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_idem ON agent_tool_calls(idempotency_key, request_hash);

CREATE TABLE IF NOT EXISTS agent_model_calls (
    call_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    step_id TEXT,
    provider TEXT NOT NULL,
    route_policy TEXT NOT NULL,
    model TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    latency_ms INTEGER,
    fallback_reason TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    cached_tokens INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_model_calls_run ON agent_model_calls(run_id);

CREATE TABLE IF NOT EXISTS agent_events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    phase TEXT NOT NULL,
    role TEXT,
    summary TEXT,
    progress_json TEXT,
    artifact_id TEXT,
    approval_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    UNIQUE(run_id, sequence)
);
CREATE INDEX IF NOT EXISTS idx_agent_events_run_seq ON agent_events(run_id, sequence);
-- Last-Event-ID 续传: 由 (run_id, event_id) 直接定位 sequence, 不再扫描事件列表。
CREATE INDEX IF NOT EXISTS idx_agent_events_run_event ON agent_events(run_id, event_id);

CREATE TABLE IF NOT EXISTS agent_memories (
    memory_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    content_summary TEXT NOT NULL,
    sensitivity TEXT NOT NULL DEFAULT 'low',
    confirmed INTEGER NOT NULL DEFAULT 0,
    withdrawn INTEGER NOT NULL DEFAULT 0,
    model_may_consume INTEGER NOT NULL DEFAULT 0,
    provenance TEXT,
    valid_until TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(kind IN ('CONFIRMED_PREFERENCE','CONFIRMED_STUDY_GOAL','CONFIRMED_CONSTRAINT','USER_APPROVED_SUMMARY')),
    CHECK(sensitivity IN ('low','medium','high'))
);
CREATE INDEX IF NOT EXISTS idx_agent_memories_user ON agent_memories(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_approvals (
    approval_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    risk_level TEXT NOT NULL,
    action_summary TEXT NOT NULL,
    -- 审批必须绑定到"具体工具 + 具体参数"，否则一次批准可以被复用到
    -- 另一门课程 / 另一种 mode / 另一组参数。
    tool_name TEXT,
    request_hash TEXT,
    -- 由 Gateway 创建（绑定到某次工具调用）时记录 call_id；
    -- 路由提前创建（如期末复习的计划生成）时为 NULL，此时按 tool+hash 校验。
    call_id TEXT,
    expires_at TEXT NOT NULL,
    resolved_at TEXT,
    decision_reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK(status IN ('PENDING','APPROVED','REJECTED','EXPIRED')),
    CHECK(risk_level IN ('AUTO_SAFE','CONFIRM_REQUIRED','MANUAL_ONLY'))
);
CREATE INDEX IF NOT EXISTS idx_agent_approvals_run ON agent_approvals(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_approvals_user_status ON agent_approvals(user_id, status);

CREATE TABLE IF NOT EXISTS agent_citations (
    citation_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    title TEXT,
    accessed_at TEXT NOT NULL,
    is_accessible INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_citations_run ON agent_citations(run_id);

CREATE TABLE IF NOT EXISTS agent_artifacts (
    artifact_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT NOT NULL,
    storage_path TEXT NOT NULL,
    download_url TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(run_id) REFERENCES agent_runs(run_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_run ON agent_artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_artifacts_user ON agent_artifacts(user_id, created_at DESC);
"""


STUDENT_GOAL_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS student_goals (
    goal_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','archived')),
    target_date TEXT,
    archived_at TEXT,
    progress_percent REAL NOT NULL DEFAULT 0.0 CHECK(progress_percent >= 0 AND progress_percent <= 100),
    milestone_count INTEGER NOT NULL DEFAULT 0 CHECK(milestone_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    idempotency_key TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_student_goals_user_status
    ON student_goals(user_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_student_goals_user_category
    ON student_goals(user_id, category);
CREATE TABLE IF NOT EXISTS student_goal_progress (
    progress_id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    progress_percent REAL NOT NULL CHECK(progress_percent >= 0 AND progress_percent <= 100),
    milestone_reached TEXT,
    occurred_at TEXT NOT NULL,
    idempotency_key TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(goal_id, idempotency_key),
    FOREIGN KEY(goal_id) REFERENCES student_goals(goal_id) ON DELETE CASCADE,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_student_goal_progress_goal
    ON student_goal_progress(goal_id, occurred_at DESC);
"""


class Database:
    """线程安全的 SQLite 包装。

    - 文件模式：每请求新连接，WAL + 短超时。
    - 内存模式：单条共享连接(必须 `check_same_thread=False`)，
      所有读写都通过同一连接，保证 schema 与数据可见性。
    """

    def __init__(self, db_path: Path | None) -> None:
        self._is_memory = db_path is None
        self._db_path = str(db_path) if db_path else ":memory:"
        self._lock = threading.RLock()
        # 内存模式：共享单连接；文件模式：None
        self._shared_conn: sqlite3.Connection | None = None
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        if self._is_memory:
            # 内存模式必须复用同一连接
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(
                    ":memory:",
                    check_same_thread=False,
                    timeout=30.0,
                )
                self._shared_conn.row_factory = sqlite3.Row
                self._shared_conn.execute("PRAGMA foreign_keys=ON;")
            return self._shared_conn
        conn = sqlite3.connect(self._db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _release(self, conn: sqlite3.Connection) -> None:
        """关闭连接(内存模式下的共享连接不关闭)。"""
        if self._is_memory:
            return
        conn.close()

    @staticmethod
    def _prepare_legacy_learning_plan_runs(conn: sqlite3.Connection) -> None:
        """补齐建索引前必须存在的旧学习计划列。"""
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(learning_plan_runs)")
        }
        if columns and "goal_id" not in columns:
            conn.execute("ALTER TABLE learning_plan_runs ADD COLUMN goal_id TEXT")

    def _init_schema(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(SCHEMA_SQL)
                conn.executescript(MULTI_ROLE_SCHEMA_SQL)
                conn.executescript(UNIVERSITY_SCHEMA_SQL)
                conn.executescript(COMMUNITY_SCHEMA_SQL)
                conn.executescript(ACADEMIC_SCHEMA_SQL)
                conn.executescript(EDU_CONNECTOR_SCHEMA_SQL)
                conn.executescript(EDU_DATA_SCHEMA_SQL)
                conn.executescript(PERSONAL_TASK_SCHEMA_SQL)
                conn.executescript(STUDY_SCHEMA_SQL)
                conn.executescript(PERSONAL_HUB_SCHEMA_SQL)
                conn.executescript(HOME_BANNER_SCHEMA_SQL)
                conn.executescript(CHAOXING_CREDENTIALS_SCHEMA_SQL)
                conn.executescript(CHAOXING_ASSESSMENT_SCHEMA_SQL)
                conn.executescript(CHAOXING_KNOWLEDGE_SCHEMA_SQL)
                conn.executescript(NOTICES_SCHEMA_SQL)
                conn.executescript(QR_AUTH_SCHEMA_SQL)
                conn.executescript(EDU_SESSION_SCHEMA_SQL)
                conn.executescript(LEARNER_EVENT_SCHEMA_SQL)
                conn.executescript(LEARNER_STATE_SCHEMA_SQL)
                self._prepare_legacy_learning_plan_runs(conn)
                conn.executescript(LEARNING_PLAN_SCHEMA_SQL)
                conn.executescript(MODEL_SHADOW_SCHEMA_SQL)
                conn.executescript(LEARNER_CONTROL_SCHEMA_SQL)
                conn.executescript(AGENT_RUNTIME_SCHEMA_SQL)
                conn.executescript(STUDENT_GOAL_SCHEMA_SQL)
                self._migrate(conn)
                conn.commit()
            finally:
                self._release(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """轻量级迁移：补齐旧库缺失的列(幂等)。"""
        for table, columns in {
            "learner_state_projection_runs": {
                "projection_kind": "TEXT NOT NULL DEFAULT 'CORE'",
                "projection_scope": "TEXT NOT NULL DEFAULT '__user__'",
            },
            "learning_plan_runs": {
                "goal_id": "TEXT",
                "core_run_id": "TEXT", "core_input_digest": "TEXT",
                "knowledge_bindings_json": "TEXT NOT NULL DEFAULT '{}'",
                "task_binding_digest": "TEXT", "task_bindings_json": "TEXT NOT NULL DEFAULT '{}'",
                "input_truncated": "INTEGER NOT NULL DEFAULT 0", "core_quality": "TEXT NOT NULL DEFAULT 'verified'",
            },
            "learning_plans": {
                "supersedes_plan_id": "TEXT", "superseded_by_plan_id": "TEXT",
                "stale_reason": "TEXT", "replan_key": "TEXT",
            },
            "learning_plan_execution_actions": {"target_task_digest": "TEXT"},
            # 用量记账:老库补列,避免只有延迟没有 token 成本。
            "agent_model_calls": {
                "prompt_tokens": "INTEGER",
                "completion_tokens": "INTEGER",
                "total_tokens": "INTEGER",
                "cached_tokens": "INTEGER",
            },
            "agent_runs": {
                "retry_of": "TEXT",
                # v2 持久化队列: 旧库补列, 默认值必须让既有行保持可领取。
                "handler_code": "TEXT",
                "handler_version": "TEXT",
                "attempt_no": "INTEGER NOT NULL DEFAULT 0",
                "next_attempt_at": "TEXT",
                "lease_owner": "TEXT",
                "lease_expires_at": "TEXT",
                "heartbeat_at": "TEXT",
                "checkpoint_json": "TEXT",
            },
            # "最近一次成功同步"必须独立于"最近一次尝试": last_synced_at 在失败时
            # 也会被刷新，用它回答"是否同步过"会把 never_synced 误报成 empty。
            "course_sync_sections": {"last_success_at": "TEXT"},
            # 审批必须绑定到具体工具与具体参数，否则一次批准可以被复用到
            # 另一门课程 / 另一种 mode / 另一组参数（旧库缺这三列）。
            "agent_approvals": {
                "tool_name": "TEXT",
                "request_hash": "TEXT",
                "call_id": "TEXT",
            },
        }.items():
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            for name, definition in columns.items():
                if name not in cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
        # 旧库回填: 当前状态为 complete/partial 的行，其 last_synced_at 就是一次
        # 成功的尝试时间。failed 行不回填 —— 无法区分"从未成功"与"曾成功后失败"，
        # 宁可少报也不要把失败当成功。
        conn.execute(
            "UPDATE course_sync_sections SET last_success_at = last_synced_at "
            "WHERE last_success_at IS NULL AND status IN ('complete', 'partial')"
        )
        # v2 队列索引依赖上面补出来的列,必须在补列之后再建,否则旧库初始化会失败。
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_claim "
            "ON agent_runs(status, next_attempt_at, lease_expires_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_lease "
            "ON agent_runs(lease_owner, lease_expires_at)"
        )
        # 管理员观测按时间窗聚合,索引让这些查询走区间扫描而不是全表扫描。
        for index_sql in (
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_created_at "
            "ON agent_runs(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_agent_runs_lease_expires "
            "ON agent_runs(lease_expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_agent_model_calls_started_at "
            "ON agent_model_calls(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_agent_tool_calls_started_at "
            "ON agent_tool_calls(started_at)",
            "CREATE INDEX IF NOT EXISTS idx_agent_approvals_created_at "
            "ON agent_approvals(created_at)",
        ):
            conn.execute(index_sql)
        shadow_result_cols = {row["name"] for row in conn.execute("PRAGMA table_info(model_shadow_results)").fetchall()}
        if "inference_source" not in shadow_result_cols:
            conn.execute(
                "ALTER TABLE model_shadow_results ADD COLUMN inference_source TEXT NOT NULL "
                "DEFAULT 'LEGACY_UNVERIFIED'"
            )
            conn.execute(
                "UPDATE model_shadow_results SET inference_source='LEGACY_UNVERIFIED'"
            )
        else:
            conn.execute(
                "UPDATE model_shadow_results SET inference_source='LEGACY_UNVERIFIED' "
                "WHERE inference_source NOT IN "
                "('REAL_MODEL','FIXTURE','DETERMINISTIC_FALLBACK','LEGACY_UNVERIFIED','NOT_OBSERVED')"
            )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_learning_plans_replan_key ON learning_plans(user_id, replan_key) WHERE replan_key IS NOT NULL")
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS learning_plan_feedback (
            feedback_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, user_id TEXT NOT NULL,
            feedback TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(plan_id, user_id, feedback)
        );
        CREATE TABLE IF NOT EXISTS learning_plan_evaluation_runs (
            evaluation_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, user_id TEXT NOT NULL,
            evaluator_version TEXT NOT NULL, input_digest TEXT NOT NULL,
            baseline_as_of TEXT NOT NULL, evaluated_as_of TEXT NOT NULL,
            metrics_json TEXT NOT NULL, warning_codes_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            FOREIGN KEY(plan_id) REFERENCES learning_plans(plan_id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(plan_id, evaluator_version, input_digest)
        );
        CREATE INDEX IF NOT EXISTS idx_learning_plan_feedback_plan ON learning_plan_feedback(plan_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_learning_plan_evaluations_plan ON learning_plan_evaluation_runs(plan_id, created_at DESC);
        """)
        conn.execute("DROP INDEX IF EXISTS idx_learner_state_runs_current")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_learner_state_runs_current "
            "ON learner_state_projection_runs(user_id, projection_kind, projection_scope) "
            "WHERE is_current = 1"
        )
        # 永久退役校园活动功能，并删除已有活动与报名记录。
        conn.executescript(
            """
            DROP TABLE IF EXISTS activity_registrations;
            DROP TABLE IF EXISTS campus_activities;
            """
        )
        # 获取 documents 表的现有列
        cur = conn.execute("PRAGMA table_info(documents)")
        existing_cols = {row["name"] for row in cur.fetchall()}
        if "is_demo" not in existing_cols:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN is_demo INTEGER DEFAULT 0"
            )
            # 旧数据默认非演示资料
            conn.execute("UPDATE documents SET is_demo = 0 WHERE is_demo IS NULL")
        # 补建索引(若旧库不存在)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_documents_is_demo ON documents(is_demo)"
        )
        # 个人待办增加 UNIQUE 约束
        cur = conn.execute("PRAGMA index_list(personal_tasks)")
        indexes = cur.fetchall()
        unique_idx_exists = False
        for idx in indexes:
            if idx["unique"] == 1:
                cur_cols = conn.execute(f"PRAGMA index_info({idx['name']})")
                cols = {c["name"] for c in cur_cols.fetchall()}
                if cols == {"user_id", "source_notice_id"}:
                    unique_idx_exists = True
                    break
        
        if not unique_idx_exists:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_personal_tasks_source_notice "
                "ON personal_tasks(user_id, source_notice_id) WHERE source_notice_id IS NOT NULL"
            )

        # 检查 courses 表新增列
        cur = conn.execute("PRAGMA table_info(courses)")
        course_cols = {row["name"] for row in cur.fetchall()}
        if "provider" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN provider TEXT")
        if "external_id" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN external_id TEXT")
        if "source_url" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN source_url TEXT")
        if "last_synced_at" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN last_synced_at TEXT")
        if "remote_teacher_name" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN remote_teacher_name TEXT")
        if "owner_user_id" not in course_cols:
            conn.execute("ALTER TABLE courses ADD COLUMN owner_user_id TEXT")
        for column, column_type in (
            ("remote_class_id", "TEXT"),
            ("remote_cpi", "TEXT"),
            ("remote_school_name", "TEXT"),
            ("remote_class_name", "TEXT"),
            ("remote_student_count", "INTEGER"),
            ("cover_url", "TEXT"),
            ("starts_at", "TEXT"),
            ("ends_at", "TEXT"),
        ):
            if column not in course_cols:
                conn.execute(f"ALTER TABLE courses ADD COLUMN {column} {column_type}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_external_id ON courses(external_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_owner_user_id ON courses(owner_user_id)")

        # 检查 users 表新增列。旧库可能在 MULTI_ROLE_SCHEMA_SQL 执行时仍缺少
        # student_number/teacher_number；先补列，再创建依赖这些列的索引。
        cur = conn.execute("PRAGMA table_info(users)")
        user_cols = {row["name"] for row in cur.fetchall()}
        for column, column_type in (
            ("student_number", "TEXT"),
            ("teacher_number", "TEXT"),
        ):
            if column not in user_cols:
                conn.execute(f"ALTER TABLE users ADD COLUMN {column} {column_type}")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_student_number ON users(student_number)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_teacher_number ON users(teacher_number)")
        # SQLite 支持部分唯一索引(NULL 不参与唯一约束)。
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_number_unique "
            "ON users(student_number) WHERE student_number IS NOT NULL"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_teacher_number_unique "
            "ON users(teacher_number) WHERE teacher_number IS NOT NULL"
        )

        # 检查 personal_tasks 表新增列
        cur = conn.execute("PRAGMA table_info(personal_tasks)")
        task_cols = {row["name"] for row in cur.fetchall()}
        if "importance" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN importance TEXT NOT NULL DEFAULT 'unknown'")
        if "source" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN source TEXT")
        if "external_id" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN external_id TEXT")
        if "course_id" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN course_id TEXT")
        if "source_url" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN source_url TEXT")
        if "last_synced_at" not in task_cols:
            conn.execute("ALTER TABLE personal_tasks ADD COLUMN last_synced_at TEXT")
        for column, column_type in (
            ("remote_submitted_at", "TEXT"),
            ("score", "REAL"),
            ("score_max", "REAL"),
            ("graded_at", "TEXT"),
        ):
            if column not in task_cols:
                conn.execute(
                    f"ALTER TABLE personal_tasks ADD COLUMN {column} {column_type}"
                )

        # 学习通考试表可能在旧库缺失(本表晚于 chaoxing_credentials 引入)。
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chaoxing_exams'"
        )
        if cur.fetchone() is None:
            conn.executescript(CHAOXING_ASSESSMENT_SCHEMA_SQL)

        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='chaoxing_knowledge_points'"
        )
        if cur.fetchone() is None:
            conn.executescript(CHAOXING_KNOWLEDGE_SCHEMA_SQL)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_id ON personal_tasks(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_status ON personal_tasks(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_deadline ON personal_tasks(deadline)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_priority ON personal_tasks(priority)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_importance ON personal_tasks(importance)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_status ON personal_tasks(user_id, status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_deadline ON personal_tasks(user_id, deadline)")

        cur = conn.execute("PRAGMA index_list(personal_tasks)")
        indexes = cur.fetchall()
        unique_idx_source_ext = False
        for idx in indexes:
            if idx["unique"] == 1:
                cur_cols = conn.execute(f"PRAGMA index_info({idx['name']})")
                cols = {c["name"] for c in cur_cols.fetchall()}
                if cols == {"user_id", "source", "external_id"}:
                    unique_idx_source_ext = True
                    break
        
        if not unique_idx_source_ext:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_personal_tasks_source_ext "
                "ON personal_tasks(user_id, source, external_id) WHERE source IS NOT NULL AND external_id IS NOT NULL"
            )

        cur = conn.execute("PRAGMA table_info(study_sessions)")
        study_cols = {row["name"] for row in cur.fetchall()}
        if "mode" not in study_cols:
            conn.execute(
                "ALTER TABLE study_sessions ADD COLUMN mode TEXT NOT NULL DEFAULT 'focus'"
            )
        if "experience_mode" not in study_cols:
            conn.execute(
                "ALTER TABLE study_sessions ADD COLUMN experience_mode TEXT NOT NULL DEFAULT 'QUIET'"
            )
        if "planned_duration_seconds" not in study_cols:
            conn.execute(
                "ALTER TABLE study_sessions ADD COLUMN planned_duration_seconds INTEGER NOT NULL DEFAULT 0"
            )
        if "behavior_summary" not in study_cols:
            conn.execute("ALTER TABLE study_sessions ADD COLUMN behavior_summary TEXT")

        # 多角色表均为 CREATE TABLE IF NOT EXISTS，已自动幂等。
        cur = conn.execute("PRAGMA table_info(users)")
        user_cols = {row["name"] for row in cur.fetchall()}
        if "university_id" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN university_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_university_id ON users(university_id)")

        # universities 表新增 level 列(本科/专科)，旧库补齐
        cur = conn.execute("PRAGMA table_info(universities)")
        uni_cols = {row["name"] for row in cur.fetchall()}
        if "level" not in uni_cols:
            conn.execute("ALTER TABLE universities ADD COLUMN level TEXT")
        if "school_code" not in uni_cols:
            conn.execute("ALTER TABLE universities ADD COLUMN school_code TEXT")
        # 教务系统连接字段(旧库缺列补齐，与 UNIVERSITY_SCHEMA_SQL 对齐)
        if "academic_system_type" not in uni_cols:
            conn.execute(
                "ALTER TABLE universities ADD COLUMN academic_system_type TEXT NOT NULL DEFAULT 'unsupported'"
            )
        if "academic_system_url" not in uni_cols:
            conn.execute("ALTER TABLE universities ADD COLUMN academic_system_url TEXT")
        if "academic_provider" not in uni_cols:
            conn.execute(
                "ALTER TABLE universities ADD COLUMN academic_provider TEXT NOT NULL DEFAULT 'unsupported'"
            )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_universities_level ON universities(level)")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_universities_school_code "
            "ON universities(school_code) WHERE school_code IS NOT NULL"
        )

        # ---- forum_posts 表补齐 extra_json / view_count 列(旧库) ----
        cur = conn.execute("PRAGMA table_info(forum_posts)")
        post_cols = {row["name"] for row in cur.fetchall()}
        if "extra_json" not in post_cols:
            conn.execute("ALTER TABLE forum_posts ADD COLUMN extra_json TEXT NOT NULL DEFAULT '{}'")
        if "view_count" not in post_cols:
            conn.execute("ALTER TABLE forum_posts ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_forum_posts_category "
            "ON forum_posts(university_id, status, category, created_at DESC)"
        )

        # ---- EduConnector 架构迁移 ----
        cur = conn.execute("PRAGMA table_info(learner_state_evidence)")
        state_evidence_cols = {row["name"] for row in cur.fetchall()}
        if state_evidence_cols and "explanation_code" not in state_evidence_cols:
            conn.execute(
                "ALTER TABLE learner_state_evidence ADD COLUMN explanation_code TEXT NOT NULL DEFAULT 'state_observed'"
            )
        self._migrate_edu_schema(conn)

    def _migrate_edu_schema(self, conn: sqlite3.Connection) -> None:
        """EduConnector 架构迁移：edu_bindings 升级 + edu_system_configs → edu_systems。"""
        cur = conn.execute("PRAGMA table_info(edu_connections)")
        connection_cols = {row["name"] for row in cur.fetchall()}
        if connection_cols and "portal_url" not in connection_cols:
            conn.execute("ALTER TABLE edu_connections ADD COLUMN portal_url TEXT")

        cur = conn.execute("PRAGMA table_info(edu_systems)")
        system_cols = {row["name"] for row in cur.fetchall()}
        if system_cols and "adapter_config" not in system_cols:
            conn.execute("ALTER TABLE edu_systems ADD COLUMN adapter_config TEXT NOT NULL DEFAULT '{}'")

        # 1. edu_bindings 旧 schema → 新 schema
        cur = conn.execute("PRAGMA table_info(edu_bindings)")
        bind_cols = {row["name"] for row in cur.fetchall()}
        if bind_cols and "edu_system_id" not in bind_cols:
            conn.execute("ALTER TABLE edu_bindings RENAME TO edu_bindings_legacy_v1")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS edu_bindings (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    edu_system_id TEXT,
                    university_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    system_type TEXT NOT NULL DEFAULT 'undergrad',
                    external_student_id TEXT,
                    external_student_name TEXT,
                    connection_status TEXT NOT NULL DEFAULT 'unbound',
                    session_type TEXT,
                    credential_ref TEXT,
                    last_authenticated_at TEXT,
                    session_expires_at TEXT,
                    last_synced_at TEXT,
                    last_sync_status TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY(university_id) REFERENCES universities(id) ON DELETE RESTRICT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO edu_bindings (
                    id, user_id, edu_system_id, university_id, provider, system_type,
                    external_student_id, external_student_name, connection_status,
                    credential_ref, last_synced_at, last_sync_status, last_error,
                    created_at, updated_at
                )
                SELECT
                    id, user_id, NULL, university_id, provider, system_type,
                    external_student_id, external_student_name,
                    COALESCE(status, 'unbound'),
                    credential_ref, last_synced_at, last_sync_status, last_error,
                    created_at, updated_at
                FROM edu_bindings_legacy_v1
                """
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_edu_bindings_user_system "
                "ON edu_bindings(user_id, edu_system_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edu_bindings_university "
                "ON edu_bindings(university_id, provider)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_edu_bindings_status "
                "ON edu_bindings(connection_status)"
            )

        # 2. edu_sync_records 旧 schema → 新 schema (加 adapter/error_code)
        cur = conn.execute("PRAGMA table_info(edu_sync_records)")
        sync_cols = {row["name"] for row in cur.fetchall()}
        if sync_cols and "adapter" not in sync_cols:
            conn.execute("ALTER TABLE edu_sync_records ADD COLUMN adapter TEXT")
        if sync_cols and "adapter_version" not in sync_cols:
            conn.execute("ALTER TABLE edu_sync_records ADD COLUMN adapter_version TEXT")
        if sync_cols and "error_code" not in sync_cols:
            conn.execute("ALTER TABLE edu_sync_records ADD COLUMN error_code TEXT")

        # 4. edu_schedule_items 扩展列迁移（课程详情完整字段 + extra_info）
        cur = conn.execute("PRAGMA table_info(edu_schedule_items)")
        sch_cols = {row["name"] for row in cur.fetchall()}
        for column, column_type in (
            ("teachers", "TEXT"),
            ("campus", "TEXT"),
            ("building", "TEXT"),
            ("classroom", "TEXT"),
            ("week_text", "TEXT"),
            ("credit", "REAL"),
            ("course_nature", "TEXT"),
            ("course_category", "TEXT"),
            ("course_type", "TEXT"),
            ("teaching_class", "TEXT"),
            ("class_name", "TEXT"),
            ("college", "TEXT"),
            ("department", "TEXT"),
            ("assessment_method", "TEXT"),
            ("exam_type", "TEXT"),
            ("total_hours", "REAL"),
            ("theory_hours", "REAL"),
            ("practice_hours", "REAL"),
            ("language", "TEXT"),
            ("note", "TEXT"),
            ("semester_id", "TEXT"),
            ("extra_info", "TEXT"),
        ):
            if column not in sch_cols:
                conn.execute(
                    f"ALTER TABLE edu_schedule_items ADD COLUMN {column} {column_type}"
                )

        # 3. edu_system_configs → edu_systems 幂等迁移
        cur = conn.execute("PRAGMA table_info(edu_systems)")
        systems_cols = {row["name"] for row in cur.fetchall()}
        if not systems_cols:
            return
        configs_exist = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='edu_system_configs'"
        ).fetchone()[0]
        if not configs_exist:
            return
        rows = conn.execute(
            """
            SELECT university_id, provider, system_type, school_code,
                   academic_system_url, sso_url, cas_url, webvpn_url,
                   login_method, captcha_type, requires_campus_network,
                   supported_features, notes, data_source, created_at, updated_at
            FROM edu_system_configs
            WHERE university_id NOT IN (
                SELECT university_id FROM edu_systems WHERE system_key = 'undergraduate-main'
            )
            """
        ).fetchall()
        now = datetime.now(timezone.utc).isoformat()
        for r in rows:
            import hashlib
            sys_id = f"esys_{hashlib.md5(r['university_id'].encode()).hexdigest()[:16]}"
            rcn = int(r["requires_campus_network"]) if r["requires_campus_network"] is not None else 0
            conn.execute(
                """
                INSERT OR IGNORE INTO edu_systems (
                    id, university_id, school_code, system_key, name, system_type,
                    provider, base_url, sso_url, vpn_url, auth_type,
                    login_execution_mode, captcha_type, requires_campus_network,
                    requires_vpn, status, verification_status, supported_features,
                    source, notes, is_mock, created_at, updated_at
                ) VALUES (?, ?, ?, 'undergraduate-main', NULL, ?, ?, ?, ?, ?, ?, 'unsupported', ?, ?, 0, 'active', 'unverified', ?, ?, ?, 0, ?, ?)
                """,
                (
                    sys_id, r["university_id"], r["school_code"],
                    r["system_type"], r["provider"],
                    r["academic_system_url"], r["sso_url"], r["webvpn_url"],
                    r["login_method"], r["captcha_type"], rcn,
                    r["supported_features"], r["data_source"], r["notes"],
                    r["created_at"] or now, r["updated_at"] or now,
                ),
            )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """事务上下文：成功提交，异常回滚。"""
        with self._lock:
            conn = self._connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                self._release(conn)

    @contextmanager
    def query(self) -> Iterator[sqlite3.Connection]:
        """只读查询上下文(自动关闭连接)。"""
        with self._lock:
            conn = self._connect()
            try:
                yield conn
            finally:
                self._release(conn)

    def dispose(self) -> None:
        """释放底层连接(主要用于测试清理)。

        - 内存模式: 关闭共享连接。
        - 文件模式: 执行 WAL checkpoint(TRUNCATE) 以便释放 -wal/-shm 文件锁,
          让外部 cleanup(如 TemporaryDirectory) 能在 Windows 上删除 db 文件。
        """
        with self._lock:
            if self._is_memory:
                if self._shared_conn is not None:
                    try:
                        self._shared_conn.close()
                    finally:
                        self._shared_conn = None
                return
            # 文件模式: 短连接做 checkpoint
            try:
                conn = sqlite3.connect(self._db_path, timeout=30.0)
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                conn.commit()
                conn.close()
            except Exception:
                # 测试清理不应因 checkpoint 失败而中断
                pass


_db_instance: Database | None = None


def init_db(settings: Settings) -> Database:
    """初始化全局 Database 单例。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(settings.database_path)
    return _db_instance


def get_db() -> Database:
    """FastAPI 依赖：返回全局 Database 实例。"""
    if _db_instance is None:
        raise RuntimeError("Database 未初始化，请先调用 init_db()")
    return _db_instance


def reset_db_for_tests() -> Database:
    """测试专用：创建一个全新的内存库并替换单例。"""
    global _db_instance
    if _db_instance is not None and _db_instance._is_memory:
        # 关闭旧的共享连接
        try:
            if _db_instance._shared_conn is not None:
                _db_instance._shared_conn.close()
        except Exception:
            pass
    _db_instance = Database(None)
    return _db_instance


__all__ = ["Database", "init_db", "get_db", "reset_db_for_tests"]
