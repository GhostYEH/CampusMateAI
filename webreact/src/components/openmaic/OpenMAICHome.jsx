import React from "react";
import { Link } from "react-router-dom";
import { Button, Panel, SectionHeading } from "../Primitives.jsx";
import { Icon } from "../Icon.jsx";
import { formatDateTime } from "../../utils/date.js";
import { buildCourseRailItems, filterOpenMAICHomeItems } from "../../features/openmaic/homeModel.js";

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

export default function OpenMAICHome({ courses = [], assignments = [], recentClassrooms = [], onQuickAsk, onCreateContent }) {
  const [query, setQuery] = React.useState("");
  const filteredRecent = filterOpenMAICHomeItems(recentClassrooms, query);
  const [selectedCourseId, setSelectedCourseId] = React.useState(courses[0]?.id || "");

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
        {filteredRecent.length ? <div className="openmaic-recent-grid">{filteredRecent.slice(0, 8).map((item) => <Link className="openmaic-recent-card" key={`${item.courseId}:${item.session_id || item.id}`} to={`/courses/${item.courseId}`}>
          <span className="openmaic-recent-card__type">{item.mode || item.type || "课堂"}</span><strong>{item.title || item.name || "未命名课堂"}</strong><small>{item.course_name || item.courseName || "课程上下文"}</small><span className="openmaic-recent-card__date">{dateText(item.updated_at || item.updatedAt || item.created_at)}</span>
        </Link>)}</div> : <div className="openmaic-home__empty openmaic-home__empty--wide"><Icon name="PhClockCounterClockwise" size={28} /><div><strong>{query ? "没有匹配的最近内容" : "还没有最近课堂"}</strong><p>{query ? "尝试换一个关键词，或从课程栏进入课程。" : "生成的课堂会在这里按最近更新时间出现。"}</p></div></div>}
      </Panel>

      <Panel className="openmaic-capability-panel">
        <SectionHeading title="内容入口" detail="能力按服务端状态逐项开放" />
        <div className="openmaic-capability-list" aria-label="内容能力状态"><span><Icon name="PhFolderSimple" size={16} />文件夹 <small>正在接入</small></span><span><Icon name="PhUploadSimple" size={16} />导入 <small>正在接入</small></span><span><Icon name="PhMagnifyingGlass" size={16} />全局搜索 <small>正在接入</small></span></div>
        <p className="muted-copy">导入能力正在接入。尚未验证的能力不会显示为可点击入口。</p>
      </Panel>
    </div>
    <CourseRail courses={courses} assignments={assignments} />
  </section>;
}
