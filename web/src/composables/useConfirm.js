import { ref } from "vue";

const state = ref({
  visible: false,
  title: "确认操作",
  message: "",
  confirmText: "确认",
  cancelText: "取消",
  danger: false,
  resolver: null,
});

export function useConfirm() {
  function confirm(options = {}) {
    state.value = {
      visible: true,
      title: options.title || "确认操作",
      message: options.message || "确定要继续吗?",
      confirmText: options.confirmText || "确认",
      cancelText: options.cancelText || "取消",
      danger: Boolean(options.danger),
      resolver: null,
    };
    return new Promise((resolve) => {
      state.value.resolver = resolve;
    });
  }
  function resolve(value) {
    if (state.value.resolver) {
      state.value.resolver(value);
      state.value.resolver = null;
    }
    state.value.visible = false;
  }
  return { state, confirm, resolve };
}