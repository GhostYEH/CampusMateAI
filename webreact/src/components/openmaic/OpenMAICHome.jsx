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
} from "../../features/openmaic/homeModel.js";
import { enterClassroomHref } from "../../features/openmaic/enterClassroomModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

function CourseRail({ courses, assignments }) {
  const items = buildCourseRailItems(courses, assignments);
  return <aside className="openmaic-home__rail" aria-label="我的课程">
    <SectionHeading title="我的课程" detail={`${items.length} 门课程`} />
    {items.length ? <div className="openmaic-course-rail">{items.map((course) => <div className="openmaic-course-rail__row" key={course.id}>
      <Link className="openmaic-course-rail__item" to={`/courses/${course.id}`}>
        <span className="openmaic-course-rail__icon" aria-hidden="true"><Icon name="PhBookOpenText" size={18} /></span>
        <span className="openmaic-course-rail__copy"><strong>{course.name}</strong><small>{[course.teacher, course.term, course.code].filter(Boolean).join(" · ")}</small></span>
        <span className="openmaic-course-rail__meta">{course.pendingCount ? <b>{course.pendingCount} 项待办</b> : <span>暂无待办</span>}{course.nextDeadline && <small>最近 {dateText(course.nextDeadline)}</small>}</span>
        <Icon name="PhArrowUpRight" size={15} aria-hidden="true" />
      </Link>
      {/* 「进入课堂」直达：不经过角色选择、模式选择，也不经过生成预览。 */}
      <Link
        className="openmaic-course-rail__enter"
        to={enterClassroomHref(course.id)}
        aria-label={`进入《${course.name}》的课堂`}
      >
        <Icon name="PhSparkle" size={15} aria-hidden="true" />进入课堂
      </Link>
    </div>)}</div> : <div className="openmaic-home__empty"><Icon name="PhBookOpen" size={24} /><p>暂无已选课程</p><small>课程同步后会显示在这里。</small></div>}
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

/** 页面视觉焦点：选择真实课程后直达课堂，不经过预览或角色配置。 */
function ClassroomEntry({ courses, selectedCourseId, onSelectCourse }) {
  const href = selectedCourseId ? enterClassroomHref(selectedCourseId) : "";
  return <Panel className="openmaic-command-panel">
    <div className="openmaic-brand-lockup" aria-label="OpenMAIC 生成式多智能体互动课堂">
      <span className="openmaic-brand-lockup__mark" aria-hidden="true"><Icon name="PhCube" size={26} weight="duotone" /></span>
      <span><strong>OpenMAIC</strong><small>Generative Learning in Multi-Agent Interactive Classroom</small></span>
    </div>
    <div className="openmaic-command-panel__head">
      <h2>进入课堂</h2>
      <p>选择一门已选课程，直接开始学习并在课堂中继续编辑内容。</p>
    </div>
    <div className="openmaic-classroom-entry">
      <CourseContextPicker courses={courses} selectedCourseId={selectedCourseId} onSelectCourse={onSelectCourse} />
      {href
        ? <Link className="button button-primary openmaic-classroom-entry__action" to={href}>
          <Icon name="PhSparkle" size={17} />进入课堂
        </Link>
        : <Button type="button" icon="PhSparkle" disabled>进入课堂</Button>}
    </div>
    <p className="openmaic-classroom-entry__hint" role="status">进入后会创建或恢复该课程的课堂；服务不可用时会在课堂页提供可操作的错误说明。</p>
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
}) {
  const [selectedCourseId, setSelectedCourseId] = React.useState(() => defaultOpenMAICCourseId(courses));
  const [secondaryTab, setSecondaryTab] = React.useState("");
  const status = describeFusionState(fusion);

  React.useEffect(() => {
    if (!courses.some((course) => String(course.id) === String(selectedCourseId))) setSelectedCourseId(defaultOpenMAICCourseId(courses));
  }, [courses, selectedCourseId]);

  function selectCourse(courseId) {
    setSelectedCourseId(courseId);
  }

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
      <ClassroomEntry
        courses={courses}
        selectedCourseId={selectedCourseId}
        onSelectCourse={selectCourse}
      />

      <Panel className="openmaic-recent-panel">
        <SectionHeading title="最近内容" detail="来自已生成的真实课堂" />
        {recentError ? <div className="openmaic-home__empty openmaic-home__empty--wide" role="status"><Icon name="PhWarningCircle" size={28} /><div><strong>最近内容暂时取不到</strong><p>{recentError}</p></div></div>
          : recentItems.length ? <div className="openmaic-recent-grid">{recentItems.slice(0, 8).map((item) => <Link className="openmaic-recent-card" key={`${item.kind}:${item.id}`} to={item.href}>
            <span className="openmaic-recent-card__type">{item.title}</span><strong>{item.courseName}</strong><small>{item.scenesCount ? `${item.scenesCount} 个场景` : "互动课堂"}</small><span className="openmaic-recent-card__date">{dateText(item.updatedAt)}</span>
          </Link>)}</div> : <div className="openmaic-home__empty openmaic-home__empty--wide"><Icon name="PhClockCounterClockwise" size={28} /><div><strong>还没有最近课堂</strong><p>生成的课堂会在这里按最近更新时间出现。</p></div></div>}
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
