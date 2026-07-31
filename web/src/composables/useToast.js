import { ref } from "vue";

const toast = ref({ visible: false, message: "", type: "success" });
let timer = null;

export function useToast() {
  function show(message, type = "success", duration = 2400) {
    toast.value = { visible: true, message, type };
    if (timer) window.clearTimeout(timer);
    timer = window.setTimeout(() => {
      toast.value.visible = false;
    }, duration);
  }
  function success(message) { show(message, "success"); }
  function error(message) { show(message, "error", 3600); }
  function info(message) { show(message, "info"); }
  function warning(message) { show(message, "warning", 3200); }
  return { toast, show, success, error, info, warning };
}

export function extractErrorMessage(err, fallback = "操作失败") {
  if (!err) return fallback;
  if (err.response?.data?.message) return err.response.data.message;
  if (err.response?.data?.detail) {
    const detail = err.response.data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    }
  }
  if (err.message) return err.message;
  return fallback;
}