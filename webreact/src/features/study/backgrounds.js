export const STUDY_BACKGROUNDS = Object.freeze([
  "/assets/study/study-lake-sunrise.png",
  "/assets/study/study-forest-stream.png",
  "/assets/study/study-sea-sunset.png",
  "/assets/study/study-rain-window.png",
  "/assets/study/study-autumn-campus.png",
]);

export function pickStudyBackground(random = Math.random) {
  const index = Math.min(STUDY_BACKGROUNDS.length - 1, Math.floor(random() * STUDY_BACKGROUNDS.length));
  return STUDY_BACKGROUNDS[Math.max(0, index)];
}
