import React from "react";
import { Link } from "react-router-dom";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import { formatDateTime } from "../../utils/date.js";
import WorkspacePanel from "./WorkspacePanel.jsx";
import {
  buildCourseRailItems,
  describeFusionState,
  filterOpenMAICHomeItems,
} from "../../features/openmaic/homeModel.js";

const dateText = (value) => formatDateTime(value, { dateStyle: "medium", timeStyle: "short" }, "时间待定");

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

export default function OpenMAICHome({
  courses = [],
  assignments = [],
  recentItems = [],
  fusion = null,
  recentError = "",
  onQuickAsk,
  onCreateContent,
}) {
  const [query, setQuery] = React.useState("");
  const filteredRecent = filterOpenMAICHomeItems(recentItems, query);
  const [selectedCourseId, setSelectedCourseId] = React.useState(courses[0]?.id || "");
  const status = describeFusionState(fusion);

  React.useEffect(() => {
    if (!courses.some((course) => String(course.id) === String(selectedCourseId))) setSelectedCourseId(courses[0]?.id || "");
  }, [courses, selectedCourseId]);

  function submitQuickAsk(event) {
    event.preventDefault();
    if (query.trim() && selectedCourseId) onQuickAsk?.(query.trim(), selectedCourseId);
  }

  return <section className="openmaic-home" aria-label="OpenMAIC 学习工作台">
    <div className="openmaic-home__main">
      <Panel className="openmaic-command-panel">
        <span className="eyebrow">OPENMAIC / CAMPUSMATE</span>
        <h2>把课程内容变成可以继续学习的课堂</h2>
        <p>从真实课程上下文开始，快速询问，或创建一份新的学习内容。</p>
        <form className="openmaic-command" onSubmit={submitQuickAsk}>
          <label className="openmaic-command__input"><Icon name="PhSparkle" size={19} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="询问课程内容，或搜索最近课堂" aria-label="询问课程内容" /></label>
          <select value={selectedCourseId} onChange={(event) => setSelectedCourseId(event.target.value)} aria-label="选择课程" disabled={!courses.length}><option value="">选择课程</option>{courses.map((course) => <option key={course.id} value={course.id}>{course.name || course.title || "未命名课程"}</option>)}</select>
          <Button type="submit" disabled={!query.trim() || !selectedCourseId}>快速询问</Button>
          <Button type="button" variant="secondary" disabled={!selectedCourseId} onClick={() => onCreateContent?.(selectedCourseId)}>创建学习内容</Button>
        </form>
      </Panel>

      <Panel className="openmaic-recent-panel">
        <SectionHeading title="最近内容" detail={query ? `${filteredRecent.length} 个匹配结果` : "来自已生成的真实课堂"} />
        {recentError ? <div className="openmaic-home__empty openmaic-home__empty--wide" role="status"><Icon name="PhWarningCircle" size={28} /><div><strong>最近内容暂时取不到</strong><p>{recentError}</p></div></div>
          : filteredRecent.length ? <div className="openmaic-recent-grid">{filteredRecent.slice(0, 8).map((item) => <Link className="openmaic-recent-card" key={`${item.kind}:${item.id}`} to={item.href}>
            <span className="openmaic-recent-card__type">{item.title}</span><strong>{item.courseName}</strong><small>{item.scenesCount ? `${item.scenesCount} 个场景` : "互动课堂"}</small><span className="openmaic-recent-card__date">{dateText(item.updatedAt)}</span>
          </Link>)}</div> : <div className="openmaic-home__empty openmaic-home__empty--wide"><Icon name="PhClockCounterClockwise" size={28} /><div><strong>{query ? "没有匹配的最近内容" : "还没有最近课堂"}</strong><p>{query ? "尝试换一个关键词，或从课程栏进入课程。" : "生成的课堂会在这里按最近更新时间出现。"}</p></div></div>}
      </Panel>

      <Panel className="openmaic-capability-panel">
        <SectionHeading title="内容入口" detail={`服务状态：${status.label}`} />
        <CapabilityList fusion={status} />
        <p className="muted-copy">{status.detail}</p>
      </Panel>

      {/* 只有服务端真实上报 workspace 能力时才渲染——未上报时不出现任何入口。 */}
      {status.canCreateWorkspace && selectedCourseId
        ? <WorkspacePanel
          courseId={selectedCourseId}
          courseName={courses.find((course) => String(course.id) === String(selectedCourseId))?.name || ""}
        />
        : null}
    </div>
    <CourseRail courses={courses} assignments={assignments} />
  </section>;
}
