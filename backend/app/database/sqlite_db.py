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
CREATE INDEX IF NOT EXISTS idx_users_student_number ON users(student_number);
CREATE INDEX IF NOT EXISTS idx_users_teacher_number ON users(teacher_number);
-- SQLite 支持部分唯一索引(NULL 不参与唯一约束)
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_student_number_unique
    ON users(student_number) WHERE student_number IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_teacher_number_unique
    ON users(teacher_number) WHERE teacher_number IS NOT NULL;

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

CREATE TABLE IF NOT EXISTS campus_activities (
    id TEXT PRIMARY KEY,
    author_id TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'campus',
    location TEXT,
    registration_deadline TEXT,
    starts_at TEXT,
    ends_at TEXT,
    capacity INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(author_id) REFERENCES users(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_campus_activities_status ON campus_activities(status);
CREATE INDEX IF NOT EXISTS idx_campus_activities_starts_at ON campus_activities(starts_at);
CREATE INDEX IF NOT EXISTS idx_campus_activities_deadline ON campus_activities(registration_deadline);

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
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user_id, source_notice_id),
    UNIQUE(user_id, source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_id ON personal_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_status ON personal_tasks(status);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_deadline ON personal_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_priority ON personal_tasks(priority);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_status ON personal_tasks(user_id, status);
CREATE INDEX IF NOT EXISTS idx_personal_tasks_user_deadline ON personal_tasks(user_id, deadline);
"""


# 学习陪伴 schema —— 学习会话 / 休息记录。
# 所有记录绑定 user_id(JWT 用户隔离)。状态机由仓库层与路由层共同校验。
STUDY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS study_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    mode TEXT NOT NULL DEFAULT 'focus',
    goal TEXT,
    related_task_id TEXT,
    started_at TEXT NOT NULL,
    paused_at TEXT,
    ended_at TEXT,
    duration_seconds INTEGER NOT NULL DEFAULT 0,
    pause_seconds INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active',
    self_report TEXT,
    self_report_tags TEXT,
    expression_signal TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_id ON study_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_study_sessions_status ON study_sessions(status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_user_status ON study_sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_study_sessions_started_at ON study_sessions(started_at);

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

CHAOXING_CREDENTIALS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS chaoxing_credentials (
    user_id TEXT PRIMARY KEY,
    encrypted_cookies TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
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
    last_synced_at TEXT NOT NULL,
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
                conn.executescript(CHAOXING_CREDENTIALS_SCHEMA_SQL)
                conn.executescript(NOTICES_SCHEMA_SQL)
                conn.executescript(QR_AUTH_SCHEMA_SQL)
                conn.executescript(EDU_SESSION_SCHEMA_SQL)
                self._migrate(conn)
                conn.commit()
            finally:
                self._release(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        """轻量级迁移：补齐旧库缺失的列(幂等)。"""
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

        # 检查 personal_tasks 表新增列
        cur = conn.execute("PRAGMA table_info(personal_tasks)")
        task_cols = {row["name"] for row in cur.fetchall()}
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
