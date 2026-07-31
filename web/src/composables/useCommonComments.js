import { ref, watch, onMounted } from "vue";

const STORAGE_KEY = "campus_teacher_common_comments";

export function useCommonComments() {
  const comments = ref([]);
  const loaded = ref(false);

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      comments.value = raw ? JSON.parse(raw) : [];
    } catch {
      comments.value = [];
    }
    loaded.value = true;
  }

  function persist() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(comments.value));
    } catch {
      /* 忽略存储失败 */
    }
  }

  function add(text) {
    const trimmed = (text || "").trim();
    if (!trimmed) return;
    if (comments.value.some((c) => c.text === trimmed)) return;
    comments.value.unshift({ id: Date.now() + Math.random().toString(36).slice(2, 6), text: trimmed });
    if (comments.value.length > 30) comments.value = comments.value.slice(0, 30);
    persist();
  }

  function remove(id) {
    comments.value = comments.value.filter((c) => c.id !== id);
    persist();
  }

  if (!loaded.value) load();

  return { comments, add, remove, load };
}