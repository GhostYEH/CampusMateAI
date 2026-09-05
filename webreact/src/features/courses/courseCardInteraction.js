const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

const formatDegrees = (value) => `${Math.round(value * 10) / 10}deg`;

export function getCourseCardPointerStyle(pointer, rect) {
  const width = Math.max(rect.width, 1);
  const height = Math.max(rect.height, 1);
  const pointerX = clamp(((pointer.clientX - rect.left) / width) * 100, 0, 100);
  const pointerY = clamp(((pointer.clientY - rect.top) / height) * 100, 0, 100);

  return {
    pointerX: `${Math.round(pointerX)}%`,
    pointerY: `${Math.round(pointerY)}%`,
    tiltX: formatDegrees((50 - pointerY) / 50 * 6),
    tiltY: formatDegrees((pointerX - 50) / 50 * 6),
  };
}

export function applyCourseCardPointer(event) {
  const card = event.currentTarget;
  const style = getCourseCardPointerStyle(event, card.getBoundingClientRect());

  card.style.setProperty("--course-pointer-x", style.pointerX);
  card.style.setProperty("--course-pointer-y", style.pointerY);
  card.style.setProperty("--course-tilt-x", style.tiltX);
  card.style.setProperty("--course-tilt-y", style.tiltY);
  card.classList.add("is-pointer-active");
}

export function resetCourseCardPointer(event) {
  const card = event.currentTarget;

  card.style.setProperty("--course-pointer-x", "50%");
  card.style.setProperty("--course-pointer-y", "50%");
  card.style.setProperty("--course-tilt-x", "0deg");
  card.style.setProperty("--course-tilt-y", "0deg");
  card.classList.remove("is-pointer-active");
}
