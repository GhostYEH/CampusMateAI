<script setup>
import { ref } from "vue";
import UiIcon from "./UiIcon.vue";
import { uploadCommunityImage, resolveAssetUrl } from "../services/studentApi";

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  max: { type: Number, default: 4 },
});
const emit = defineEmits(["update:modelValue"]);
const uploading = ref(0);
const error = ref("");

async function onPick(e) {
  const files = Array.from(e.target.files || []);
  if (!files.length) return;
  error.value = "";
  const remain = props.max - props.modelValue.length;
  if (files.length > remain) error.value = `最多 ${props.max} 张，已选 ${props.modelValue.length} 张`;
  for (const file of files.slice(0, remain)) {
    uploading.value++;
    try {
      const res = await uploadCommunityImage(file);
      emit("update:modelValue", [...props.modelValue, res.url]);
    } catch (err) {
      error.value = err.response?.data?.message || "上传失败";
    } finally {
      uploading.value--;
    }
  }
  e.target.value = "";
}
function remove(idx) {
  const next = [...props.modelValue];
  next.splice(idx, 1);
  emit("update:modelValue", next);
}
</script>
<template>
  <div class="img-uploader">
    <div class="img-uploader-grid">
      <div v-for="(url, i) in modelValue" :key="url + i" class="img-uploader-item">
        <img :src="resolveAssetUrl(url)" alt="帖子图片" />
        <button type="button" class="img-uploader-remove" @click="remove(i)"><UiIcon name="PhX" :size="14" /></button>
      </div>
      <label v-if="modelValue.length < max" class="img-uploader-add">
        <UiIcon name="PhImage" :size="22" />
        <span v-if="uploading > 0">上传中…</span>
        <span v-else>添加图片</span>
        <input type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple @change="onPick" hidden />
      </label>
    </div>
    <p v-if="error" class="img-uploader-error">{{ error }}</p>
  </div>
</template>