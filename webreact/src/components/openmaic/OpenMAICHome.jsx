import React from "react";
import { Link } from "react-router-dom";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import { formatDateTime } from "../../utils/date.js";
import WorkspacePanel from "./WorkspacePanel.jsx";
import DiscoveryPanel from "./DiscoveryPanel.jsx";
import MaterialsPanel from "./MaterialsPanel.jsx";
import {
  buildCourseRailItems,
  defaultOpenMAICCourseId,
  describeFusionState,
  filterOpenMAICHomeItems,
} from "../../features/openmaic/homeModel.js";
import { quickAskRejection } from "../../features/openmaic/quickAskModel.js";
import {
  DEFAULT_SELECTED_ROLE_IDS,
  OPENMAIC_AGENT_ROLES,
  normalizeSelectedRoleIds,
  selectedRoles,
} from "../../features/openmaic/roleModel.js";
import {
  loadOpenMAICAgentSettings,
  saveOpenMAICAgentSettings,
} from "../../features/openmaic/agentSettingsModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

/** 附件接受的文件类型与辅导页保持一致：只收可解析的文本类文件。 */
const ATTACHMENT_ACCEPT = ".txt,.md,.csv,.json,text/plain,text/markdown,text/csv,application/json";

function CourseRail({ courses, assignments }) {
  const items = buildCourseRailItems(courses, assignments);
  return <aside className="openmaic-home__rail" aria-label="我的课程">
    <SectionHeading title="我的课程" detail={`${items.length} 门课程`} />
    {items.length ? <div className="openmaic-course-rail">{items.map((course) => <Link className="openmaic-course-rail__item" key={course.id} to={`/courses/${course.id}`}>
      <span className="openmaic-course-rail__icon" aria-hidden="true"><Icon name="PhBookOpenText" size={18} /></span>
      <span className="openmaic-course-rail__copy"><strong>{course.name}</strong><small>{[course.teacher, course.term, course.code].filter(Boolean).join(" · ")}</small></span>
      <span className="openmaic-course-rail__meta">{course.pendingCount ? <b>{course.pendingCount} 项待办</b> : <span>暂无待办</span>}{course.nextDeadline && <small>最近 {dateText(course.nextDeadline)}</small>}</span>
      <Icon name="PhArrowUpRight" size={15} aria-hidden="true" />
    </Link>)}</div> : <div className="openmaic-home__empty"><Icon name="PhBookOpen" size={24} /><p>暂无已选课程</p><small>课程同步后会显示在这里。</small></div>}
  </aside>;
}

/**
 * 能力入口。每一项都由**服务端真实上报的 capability** 决定是否可点，
 * 未上报的能力显示为不可用并说明原因，绝不出现"点了没反应"的空入口。
 */
function CapabilityList({ fusion }) {
  const entries = [
    { key: "folder", icon: "PhFolderSimple", label: "文件夹", enabled: fusion.canBrowseFolders },
    { key: "import", icon: "PhUploadSimple", label: "导入", enabled: fusion.canImport },
    { key: "search", icon: "PhMagnifyingGlass", label: "全局搜索", enabled: fusion.canSearch },
    { key: "workspace", icon: "PhSquaresFour", label: "学习工作台", enabled: fusion.canCreateWorkspace },
  ];
  return <div className="openmaic-capability-list" aria-label="内容能力状态">
    {entries.map((entry) => <span key={entry.key} className={entry.enabled ? "is-ready" : "is-closed"}>
      <Icon name={entry.icon} size={16} />{entry.label}
      <small>{entry.enabled ? "可用" : fusion.label}</small>
    </span>)}
  </div>;
}

function ProviderList({ providerStatus }) {
  const labels = { llm: "模型", web_search: "联网搜索", image: "图片", video: "视频", tts: "TTS", render: "渲染", external_3d: "外部 3D" };
  if (!providerStatus) return <p className="muted-copy">Provider 状态暂时取不到，相关入口保持关闭。</p>;
  if (providerStatus.state === "disabled") return <p className="muted-copy">Provider 未启用；课程和已有内容仍可用。</p>;
  return <div className="openmaic-capability-list" aria-label="Provider 能力状态">{Object.entries(labels).map(([key, label]) => <span key={key} className={providerStatus.providers?.[key] ? "is-ready" : "is-closed"}><Icon name={providerStatus.providers?.[key] ? "PhCheckCircle" : "PhMinusCircle"} size={16} />{label}<small>{providerStatus.providers?.[key] ? "已配置" : "未配置"}</small></span>)}</div>;
}

function AgentRolePicker({ mode, onModeChange, selectedRoleIds, onToggle }) {
  const [open, setOpen] = React.useState(false);
  const triggerRef = React.useRef(null);
  const selected = selectedRoles(selectedRoleIds);
  const selectedNames = selected.filter((role) => !role.required).map((role) => role.name);
  React.useEffect(() => {
    if (!open) return undefined;
    function onKeyDown(event) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open]);
  return <div className="openmaic-role-picker">
    <button
      type="button"
      ref={triggerRef}
      className="openmaic-role-picker__trigger"
      aria-expanded={open}
      aria-controls="openmaic-role-picker-panel"
      onClick={() => setOpen((value) => !value)}
    >
      <span className="openmaic-role-picker__avatars" aria-hidden="true">
        {selected.slice(0, 3).map((role) => <span key={role.id} style={{ background: role.color }}>{role.short}</span>)}
      </span>
      <span className="openmaic-role-picker__summary">课堂角色配置<small>{mode === "auto" ? "自动生成" : `${selectedNames.length + 1} 位角色`}</small></span>
      <Icon name={open ? "PhCaretUp" : "PhCaretDown"} size={15} />
    </button>
    {open ? <div id="openmaic-role-picker-panel" className="openmaic-role-picker__panel" role="dialog" aria-modal="false" aria-label="课堂角色配置">
      <div className="openmaic-role-picker__head"><div><strong>课堂角色配置</strong><span>选择参与这次学习内容的角色</span></div><button type="button" className="openmaic-role-picker__close" aria-label="关闭课堂角色配置" onClick={() => { setOpen(false); triggerRef.current?.focus(); }}><Icon name="PhX" size={14} /></button></div>
      <div className="openmaic-role-picker__modes" role="tablist" aria-label="角色模式">
        <button type="button" role="tab" aria-selected={mode === "preset"} className={mode === "preset" ? "is-active" : ""} onClick={() => onModeChange("preset")}>预设模式</button>
        <button type="button" role="tab" aria-selected={mode === "auto"} className={mode === "auto" ? "is-active" : ""} onClick={() => onModeChange("auto")}><Icon name="PhSparkle" size={13} />自动生成</button>
      </div>
      {mode === "preset"
        ? <div className="openmaic-role-picker__list">{OPENMAIC_AGENT_ROLES.map((role) => {
          const checked = selectedRoleIds.includes(role.id) || role.required;
          return <button type="button" key={role.id} className={`openmaic-role-row${checked ? " is-selected" : ""}`} onClick={() => onToggle(role.id)} aria-pressed={checked} disabled={role.required}>
            <span className={`openmaic-role-row__check${checked ? " is-checked" : ""}`}>{checked ? "✓" : ""}</span>
            <span className="openmaic-role-row__avatar" style={{ background: role.color }}>{role.short}</span>
            <span className="openmaic-role-row__name">{role.name}<small>{role.role}</small></span>
            {role.required ? <small className="openmaic-role-row__required">固定{role.voice ? ` · ${role.voice}音色` : ""}</small> : null}
          </button>;
        })}</div>
        : <div className="openmaic-role-picker__auto"><span className="openmaic-role-picker__auto-icon"><Icon name="PhShuffle" size={18} /></span><p>由 OpenMAIC 根据课程主题自动安排课堂角色。</p></div>}
    </div> : null}
  </div>;
}

/**
 * 课程列表可能有数十门课。原生 select 的弹层由浏览器接管，无法限制高度或保证
 * 在窄屏里不覆盖输入区；这里使用受控 listbox，并在选择后立即收起。
 */
function CourseContextPicker({ courses, selectedCourseId, onSelectCourse }) {
  const [open, setOpen] = React.useState(false);
  const [menuPlacement, setMenuPlacement] = React.useState({ upward: false, maxHeight: 360 });
  const rootRef = React.useRef(null);
  const triggerRef = React.useRef(null);
  const listboxId = React.useId();
  const selectedCourse = courses.find((course) => String(course.id) === String(selectedCourseId));
  const selectedName = selectedCourse?.name || selectedCourse?.title || "选择课程";

  const positionMenu = React.useCallback(() => {
    const rect = triggerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const gap = 8;
    const below = Math.max(0, Math.floor(window.innerHeight - rect.bottom - gap));
    const above = Math.max(0, Math.floor(rect.top - gap));
    // 优先向下展开；只有下方不足以显示一行且上方更宽裕时才翻转，避免菜单
    // 盖住标题。无论方向都把高度限制为真实可用视口空间。
    const upward = below < 96 && above > below;
    setMenuPlacement({ upward, maxHeight: Math.min(360, upward ? above : below) });
  }, []);

  React.useEffect(() => {
    if (!open) return undefined;
    function closeOnOutsidePointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    function closeOnEscape(event) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    function repositionOnResize() {
      positionMenu();
    }
    document.addEventListener("pointerdown", closeOnOutsidePointer);
    document.addEventListener("keydown", closeOnEscape);
    window.addEventListener("resize", repositionOnResize);
    return () => {
      document.removeEventListener("pointerdown", closeOnOutsidePointer);
      document.removeEventListener("keydown", closeOnEscape);
      window.removeEventListener("resize", repositionOnResize);
    };
  }, [open, positionMenu]);

  function toggleMenu() {
    if (open) {
      setOpen(false);
      return;
    }
    positionMenu();
    setOpen(true);
  }

  function choose(courseId) {
    onSelectCourse(String(courseId));
    setOpen(false);
    triggerRef.current?.focus();
  }

  return <div ref={rootRef} className="openmaic-course-picker">
    <button
      ref={triggerRef}
      type="button"
      className="openmaic-course-picker__trigger"
      disabled={!courses.length}
      aria-label="选择课程上下文"
      aria-haspopup="listbox"
      aria-controls={listboxId}
      aria-expanded={open}
      onClick={toggleMenu}
    >
      <Icon name="PhBookOpenText" size={16} aria-hidden="true" />
      <span>{selectedName}</span>
      <Icon name={open ? "PhCaretUp" : "PhCaretDown"} size={14} aria-hidden="true" />
    </button>
    {open ? <div id={listboxId} className={`openmaic-course-picker__menu${menuPlacement.upward ? " is-upward" : ""}`} style={{ maxHeight: menuPlacement.maxHeight }} role="listbox" aria-label="选择课程上下文">
      {courses.map((course) => {
        const courseId = String(course.id);
        const name = course.name || course.title || "未命名课程";
        const selected = courseId === String(selectedCourseId);
        return <button
          type="button"
          key={courseId}
          role="option"
          aria-selected={selected}
          data-course-id={courseId}
          className={selected ? "is-selected" : ""}
          onClick={() => choose(courseId)}
        >
          <span>{name}</span>
          {selected ? <Icon name="PhCheck" size={15} aria-hidden="true" /> : null}
        </button>;
      })}
    </div> : null}
  </div>;
}

/**
 * 页面视觉焦点：居中的课程学习输入工作区。
 *
 * 这里是唯一的提交入口，因此三件事必须同时成立：可提交性由 `quickAskRejection`
 * 与按钮 disabled 同源决定（不会"亮着但点了没反应"）；失败只显示在输入区下方
 * （不替换课程内容）；失败后问题文本与课程选择原样保留。
 */
function AskWorkspace({
  courses,
  selectedCourseId,
  onSelectCourse,
  query,
  onQuery,
  webSearch,
  onWebSearch,
  attachment,
  onAttachment,
  busy,
  error,
  status,
  canCreateContent,
  onCreateContent,
  onSubmit,
  agentMode,
  selectedRoleIds,
  onModeChange,
  onToggleRole,
}) {
  const attachmentInput = React.useRef(null);
  const rejection = quickAskRejection({ query, courseId: selectedCourseId, busy });
  return <Panel className="openmaic-command-panel">
    <div className="openmaic-brand-lockup" aria-label="OpenMAIC 生成式多智能体互动课堂">
      <span className="openmaic-brand-lockup__mark" aria-hidden="true"><Icon name="PhCube" size={26} weight="duotone" /></span>
      <span><strong>OpenMAIC</strong><small>Generative Learning in Multi-Agent Interactive Classroom</small></span>
    </div>
    <div className="openmaic-command-panel__head">
      <h2>你好，同学</h2>
      <p>输入你想学习的内容，OpenMAIC 会和你一起生成一堂可讲解、可继续编辑的互动课堂。</p>
    </div>

    <form className="openmaic-ask" onSubmit={(event) => { event.preventDefault(); if (!rejection) onSubmit(); }}>
      <div className="openmaic-ask__main">
        <label className="openmaic-ask__field">
          <span className="openmaic-ask__label">问题或学习需求</span>
          <textarea
            className="openmaic-ask__input"
            value={query}
            rows={3}
            placeholder="例如：用 10 分钟讲清进程和线程的区别…"
            onChange={(event) => onQuery(event.target.value)}
          />
        </label>

        <div className="openmaic-ask__tools">
          <input
            ref={attachmentInput}
            className="reference-file-input"
            type="file"
            accept={ATTACHMENT_ACCEPT}
            aria-label="选择学习资料附件"
            onChange={(event) => onAttachment(event.target.files?.[0] || null)}
          />
          {attachment
            ? <span className="openmaic-ask__chip">
              <Icon name="PhFileText" size={15} />{attachment.name}
              <button
                type="button"
                aria-label="移除附件"
                onClick={() => { onAttachment(null); if (attachmentInput.current) attachmentInput.current.value = ""; }}
              ><Icon name="PhX" size={13} /></button>
            </span>
            : <button type="button" className="openmaic-ask__tool" aria-label="添加学习资料附件" onClick={() => attachmentInput.current?.click()}>
              <Icon name="PhPaperclip" size={18} />附件
            </button>}
          <button
            type="button"
            className={`openmaic-ask__tool${webSearch ? " is-active" : ""}`}
            aria-pressed={webSearch}
            onClick={() => onWebSearch(!webSearch)}
          ><Icon name="PhMagnifyingGlass" size={18} />联网搜索</button>

          <div className="openmaic-ask__actions">
            {canCreateContent
              ? <Button type="button" variant="secondary" icon="PhSquaresFour" disabled={!selectedCourseId} onClick={() => onCreateContent(selectedCourseId)}>创建学习内容</Button>
              : null}
            <Button type="submit" icon="PhSparkle" disabled={Boolean(rejection)}>{busy ? "正在准备…" : "快速询问"}</Button>
          </div>
        </div>
      </div>

      <aside className="openmaic-ask__side">
        <AgentRolePicker
          mode={agentMode}
          onModeChange={onModeChange}
          selectedRoleIds={selectedRoleIds}
          onToggle={onToggleRole}
        />
        <CourseContextPicker courses={courses} selectedCourseId={selectedCourseId} onSelectCourse={onSelectCourse} />
      </aside>
    </form>

    {/* 局部错误：只说明这一次操作出了什么问题，并给出可执行的下一步。 */}
    {error
      ? <div className="openmaic-ask__error" role="alert">
        <Icon name="PhWarningCircle" size={18} />
        <div>
          <strong>{error.message}</strong>
          <div className="openmaic-ask__error-actions">{error.retryable ? <button type="button" onClick={onSubmit}>重试</button> : null}</div>
        </div>
      </div>
      : null}

    {/* 能力状态：受管服务没就绪时明确说清"哪些入口关了、哪些还能用"。 */}
    <p className="openmaic-ask__hint" role="status">
      {status.state === "ready"
        ? "受管服务已就绪；提问会带上所选课程的上下文。"
        : `${status.detail}课程列表、课程详情与已有内容不受影响。`}
    </p>
  </Panel>;
}

/** 次级功能：能力驱动、按需挂载，不再和主输入区争夺首屏。 */
function SecondaryPanels({
  tabs,
  activeTab,
  onSelectTab,
  selectedCourseId,
  selectedCourseName,
  status,
  providerStatus,
}) {
  function onKeyDown(event) {
    const index = tabs.findIndex((tab) => tab.key === activeTab);
    if (index < 0) return;
    let next = null;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    if (next === null) return;
    event.preventDefault();
    onSelectTab(tabs[next].key);
    document.getElementById(`openmaic-tab-${tabs[next].key}`)?.focus();
  }

  return <Panel className="openmaic-secondary">
    <SectionHeading title="更多学习工具" detail="按需展开，未就绪的能力不会出现在这里" />
    <div className="openmaic-tabs" role="tablist" aria-label="更多学习工具" onKeyDown={onKeyDown}>
      {tabs.map((tab) => <button
        key={tab.key}
        id={`openmaic-tab-${tab.key}`}
        type="button"
        role="tab"
        className={tab.key === activeTab ? "is-active" : ""}
        aria-selected={tab.key === activeTab}
        aria-controls={`openmaic-panel-${tab.key}`}
        tabIndex={tab.key === activeTab ? 0 : -1}
        onClick={() => onSelectTab(tab.key)}
      ><Icon name={tab.icon} size={16} />{tab.label}</button>)}
    </div>

    <div className="openmaic-tabs__panel" id={`openmaic-panel-${activeTab}`} role="tabpanel" aria-labelledby={`openmaic-tab-${activeTab}`} tabIndex={0}>
      {activeTab === "workspace" && status.canCreateWorkspace && selectedCourseId
        ? <WorkspacePanel
          courseId={selectedCourseId}
          courseName={selectedCourseName}
          canFile={status.canBrowseFolders}
          canEdit={status.canEdit}
          canExportArchive={status.canExportArchive}
          canImportArchive={status.canImportArchive}
          canExportMarkdown={status.canExportMarkdown}
          canExportDocx={status.canExportDocx}
          canExportPptx={status.canExportPptx}
          canExportVideo={status.canExportVideo}
          canImportPptx={status.canImportPptx}
        />
        : null}

      {activeTab === "discovery" && selectedCourseId && (status.canBrowseFolders || status.canSearch)
        ? <DiscoveryPanel
          courseId={selectedCourseId}
          canBrowseFolders={status.canBrowseFolders}
          canSearch={status.canSearch}
        />
        : null}

      {activeTab === "materials" && status.canManageMaterials && selectedCourseId
        ? <MaterialsPanel courseId={selectedCourseId} canManageMaterials={status.canManageMaterials} />
        : null}

      {activeTab === "service"
        ? <div className="openmaic-service-status">
          <p className="muted-copy">服务状态：{status.label}。这里只展示能力与配置与否，不展示密钥或内部地址。</p>
          <CapabilityList fusion={status} />
          <ProviderList providerStatus={providerStatus} />
        </div>
        : null}
    </div>
  </Panel>;
}

export default function OpenMAICHome({
  courses = [],
  assignments = [],
  recentItems = [],
  fusion = null,
  providerStatus = null,
  recentError = "",
  quickAskError = null,
  quickAskBusy = false,
  onQuickAsk,
  onCourseChange,
  onCreateContent,
}) {
  const [query, setQuery] = React.useState("");
  const [webSearch, setWebSearch] = React.useState(false);
  const [attachment, setAttachment] = React.useState(null);
  const [selectedCourseId, setSelectedCourseId] = React.useState(() => defaultOpenMAICCourseId(courses));
  const initialAgentSettings = React.useMemo(() => loadOpenMAICAgentSettings(), []);
  const [agentMode, setAgentMode] = React.useState(initialAgentSettings.mode);
  const [selectedRoleIds, setSelectedRoleIds] = React.useState(initialAgentSettings.selectedRoleIds || DEFAULT_SELECTED_ROLE_IDS);
  const [secondaryTab, setSecondaryTab] = React.useState("");
  const filteredRecent = filterOpenMAICHomeItems(recentItems, query);
  const status = describeFusionState(fusion);

  React.useEffect(() => {
    if (!courses.some((course) => String(course.id) === String(selectedCourseId))) setSelectedCourseId(defaultOpenMAICCourseId(courses));
  }, [courses, selectedCourseId]);

  React.useEffect(() => {
    saveOpenMAICAgentSettings({ mode: agentMode, selectedRoleIds });
  }, [agentMode, selectedRoleIds]);

  /** 课程切换必须通知外层：在途的快速询问要据此作废。 */
  function selectCourse(courseId) {
    setSelectedCourseId(courseId);
    onCourseChange?.(courseId);
  }

  const submit = () => onQuickAsk?.(query.trim(), selectedCourseId, {
    webSearch,
    attachment,
    mode: agentMode,
    selectedRoleIds: normalizeSelectedRoleIds(selectedRoleIds),
  });
  const toggleRole = (roleId) => setSelectedRoleIds((current) => current.includes(roleId)
    ? (roleId === "default-1" ? current : current.filter((id) => id !== roleId))
    : [...current, roleId]);
  const selectedCourseName = courses.find((course) => String(course.id) === String(selectedCourseId))?.name || "";

  // 次级导航只列**真实存在**的入口：能力没上报就不出现，而不是渲染一个必然
  // 失败的按钮。"服务状态"始终可看，它是诊断而不是能力。
  const tabs = [
    status.canCreateWorkspace || status.canBrowseFolders
      ? { key: "workspace", label: "学习工作台", icon: "PhSquaresFour" } : null,
    status.canBrowseFolders || status.canSearch
      ? { key: "discovery", label: "文件夹与搜索", icon: "PhFolderSimple" } : null,
    status.canManageMaterials
      ? { key: "materials", label: "课程资料", icon: "PhFileText" } : null,
    { key: "service", label: "服务状态", icon: "PhPulse" },
  ].filter(Boolean);
  const activeTab = tabs.some((tab) => tab.key === secondaryTab) ? secondaryTab : tabs[0].key;

  return <section className="openmaic-home" aria-label="OpenMAIC 学习工作台">
    <div className="openmaic-home__main">
      <AskWorkspace
        courses={courses}
        selectedCourseId={selectedCourseId}
        onSelectCourse={selectCourse}
        query={query}
        onQuery={setQuery}
        webSearch={webSearch}
        onWebSearch={setWebSearch}
        attachment={attachment}
        onAttachment={setAttachment}
        busy={quickAskBusy}
        error={quickAskError}
        status={status}
        canCreateContent={status.canCreateWorkspace && status.capabilities.includes("generation")}
        onCreateContent={(courseId) => onCreateContent?.(courseId)}
        onSubmit={submit}
        agentMode={agentMode}
        selectedRoleIds={selectedRoleIds}
        onModeChange={setAgentMode}
        onToggleRole={toggleRole}
      />

      <Panel className="openmaic-recent-panel">
        <SectionHeading title="最近内容" detail={query ? `${filteredRecent.length} 个匹配结果` : "来自已生成的真实课堂"} />
        {recentError ? <div className="openmaic-home__empty openmaic-home__empty--wide" role="status"><Icon name="PhWarningCircle" size={28} /><div><strong>最近内容暂时取不到</strong><p>{recentError}</p></div></div>
          : filteredRecent.length ? <div className="openmaic-recent-grid">{filteredRecent.slice(0, 8).map((item) => <Link className="openmaic-recent-card" key={`${item.kind}:${item.id}`} to={item.href}>
            <span className="openmaic-recent-card__type">{item.title}</span><strong>{item.courseName}</strong><small>{item.scenesCount ? `${item.scenesCount} 个场景` : "互动课堂"}</small><span className="openmaic-recent-card__date">{dateText(item.updatedAt)}</span>
          </Link>)}</div> : <div className="openmaic-home__empty openmaic-home__empty--wide"><Icon name="PhClockCounterClockwise" size={28} /><div><strong>{query ? "没有匹配的最近内容" : "还没有最近课堂"}</strong><p>{query ? "尝试换一个关键词，或从课程列表进入课程。" : "生成的课堂会在这里按最近更新时间出现。"}</p></div></div>}
      </Panel>

      <SecondaryPanels
        tabs={tabs}
        activeTab={activeTab}
        onSelectTab={setSecondaryTab}
        selectedCourseId={selectedCourseId}
        selectedCourseName={selectedCourseName}
        status={status}
        providerStatus={providerStatus}
      />

      <CourseRail courses={courses} assignments={assignments} />
    </div>
  </section>;
}
