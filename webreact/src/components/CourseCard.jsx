import { Link } from "react-router-dom";
import { Icon } from "./Icon.jsx";
import { applyCourseCardPointer, resetCourseCardPointer } from "../features/courses/courseCardInteraction.js";

export function CourseCard({ course, progress = null }) {
  return (
    <Link
      className="course-card"
      to={`/courses/${course.id}`}
      onPointerMove={applyCourseCardPointer}
      onPointerLeave={resetCourseCardPointer}
    >
      <span className="course-cover" aria-hidden="true"><Icon name="PhBookOpenText" size={30} /></span>
      <div className="course-card-copy">
        <span className="eyebrow">{course.code || course.semester || "CURRENT COURSE"}</span>
        <h2>{course.name || "未命名课程"}</h2>
        <p>{course.teacher_name || course.teacher || "教师信息待补充"}</p>
        <small>{course.class_name || course.schedule || course.semester || "进入课程查看详情"}</small>
        {progress !== null && <div className="course-progress"><i style={{ width: `${progress}%` }} /><span>{progress}% 提交进度</span></div>}
      </div>
      <Icon name="PhArrowUpRight" className="course-arrow" aria-hidden="true" />
    </Link>
  );
}
