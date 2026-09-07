export const STUDY_SCENES = Object.freeze([
  { key: "rain", label: "雨景", caption: "林间雨声", asset: "/assets/study/summer-rain.webp", alt: "雨中的林间小屋" },
  { key: "snow", label: "雪景", caption: "安静一点", asset: "/assets/study/summer-snow.webp", alt: "雪山窗边的学习空间" },
  { key: "cloud", label: "暖云", caption: "松弛推进", asset: "/assets/study/summer-cloud.webp", alt: "雨幕中的暖色窗景" },
  { key: "bamboo", label: "竹雾", caption: "溪声慢慢", asset: "/assets/study/study-bamboo-mist.png", alt: "晨雾中的竹林溪流" },
  { key: "coast", label: "海岸", caption: "晚风留白", asset: "/assets/study/study-coastal-dusk.png", alt: "蓝调时刻的海岸草坡" },
]);

export const STUDY_SCENE_ASSETS = Object.freeze(Object.fromEntries(STUDY_SCENES.map(({ key, asset }) => [key, asset])));

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
