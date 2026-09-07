export const STUDY_SCENE_ASSETS = Object.freeze({
  rain: "/assets/study/summer-rain.webp",
  snow: "/assets/study/summer-snow.webp",
  cloud: "/assets/study/summer-cloud.webp",
});

export function readStudyScene(storage = globalThis.localStorage) {
  const value = storage?.getItem("campus_study_scene");
  return Object.hasOwn(STUDY_SCENE_ASSETS, value) ? value : "rain";
}

export function saveStudyScene(scene, storage = globalThis.localStorage) {
  const next = Object.hasOwn(STUDY_SCENE_ASSETS, scene) ? scene : "rain";
  storage?.setItem("campus_study_scene", next);
  if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("campus-study-scene-change", { detail: next }));
  return next;
}
