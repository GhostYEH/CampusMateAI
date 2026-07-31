<script setup>
import UiIcon from "../UiIcon.vue";
import { useConfirm } from "../../composables/useConfirm";
const { state, resolve } = useConfirm();
</script>
<template>
  <Teleport to="body">
    <Transition name="tch-modal">
      <div v-if="state.visible" class="tch-confirm-overlay" @click.self="resolve(false)">
        <section class="tch-confirm" role="alertdialog" aria-modal="true">
          <div class="tch-confirm-icon" :class="{ danger: state.danger }">
            <UiIcon :name="state.danger ? 'PhWarningCircle' : 'PhQuestion'" :size="26" weight="fill" />
          </div>
          <h3>{{ state.title }}</h3>
          <p>{{ state.message }}</p>
          <div class="tch-confirm-actions">
            <button class="secondary-button" @click="resolve(false)">
              {{ state.cancelText }}
            </button>
            <button
              class="primary-button"
              :class="{ danger: state.danger }"
              @click="resolve(true)"
            >
              {{ state.confirmText }}
            </button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>