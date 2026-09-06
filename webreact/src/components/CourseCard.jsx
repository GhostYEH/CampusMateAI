import { Link } from "react-router-dom";
import { Icon } from "./Icon.jsx";
import { applyCourseCardPointer, getCourseCardPresentation, resetCourseCardPointer } from "../features/courses/courseCardInteraction.js";

export function CourseCard({ course, progress = null, className = "", ...props }) {
  const card = getCourseCardPresentation(course, progress);

  return (
    <Link
      {...props}
      className={`course-card course-profile-card ${className}`.trim()}
      to={`/courses/${course.id}`}
      onPointerMove={applyCourseCardPointer}
      onPointerLeave={resetCourseCardPointer}
    >
      <span className="course-profile-card__noise" aria-hidden="true" />
      <div className="course-profile-card__surface">
        <header className="course-profile-card__header">
          <span className="course-cover" aria-hidden="true"><Icon name="PhBookOpenText" size={28} /></span>
          <span className="course-profile-card__code">{card.code}</span>
          <Icon name="PhArrowUpRight" className="course-arrow" aria-hidden="true" />
        </header>
        <div className="course-card-copy">
          <span className="course-profile-card__label">我的课程</span>
          <h2>{card.name}</h2>
          <p>{card.teacher}</p>
          <small>{card.detail}</small>
        </div>
        <footer className="course-profile-card__footer">
          {card.progress !== null && <div className="course-progress"><i style={{ width: `${card.progress}%` }} /><span>{card.progressText}</span></div>}
          <span className="course-profile-card__action">进入课程 <Icon name="PhArrowRight" size={14} /></span>
        </footer>
      </div>
    </Link>
  );
}
