<script setup>
import UiIcon from "./UiIcon.vue";
import { useConfirm } from "../composables/useConfirm";

const { state, resolve } = useConfirm();
</script>

<template>
  <Teleport to="body">
    <Transition name="app-modal">
      <div v-if="state.visible" class="app-confirm-overlay" @click.self="resolve(false)">
        <section class="app-confirm" role="alertdialog" aria-modal="true">
          <div class="app-confirm-icon" :class="{ danger: state.danger }">
            <UiIcon :name="state.danger ? 'PhWarningCircle' : 'PhQuestion'" :size="26" weight="fill" />
          </div>
          <h3>{{ state.title }}</h3>
          <p>{{ state.message }}</p>
          <div class="app-confirm-actions">
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
