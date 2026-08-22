<script setup>
import FooterInfo from "./FooterInfo.vue";
import InteractiveBrand from "./InteractiveBrand.vue";
</script>

<template>
  <section class="home-reveal-shell" aria-label="CampusMate 首页内容与品牌页脚">
    <div class="home-brand-underlay">
      <InteractiveBrand />
    </div>
    <div class="home-foreground">
      <slot />
      <FooterInfo />
    </div>
  </section>
</template>

<style scoped>
.home-reveal-shell {
  --home-brand-stage-height: clamp(340px, 40vh, 460px);
  --home-sidebar-width: var(--sidebar-width, 282px);
  position: relative;
  width: 100%;
}

.home-brand-underlay {
  position: fixed;
  z-index: 0;
  left: var(--home-sidebar-width);
  right: 0;
  bottom: 0;
  height: var(--home-brand-stage-height);
  pointer-events: auto;
}

.student-layout.collapsed .home-brand-underlay {
  --home-sidebar-width: var(--sidebar-collapsed-width, 82px);
}

.student-layout.collapsed .home-reveal-shell {
  --home-sidebar-width: var(--sidebar-collapsed-width, 82px);
}

.home-foreground {
  width: calc(100vw - var(--home-sidebar-width));
  margin-left: calc((100% - (100vw - var(--home-sidebar-width))) / 2);
  position: relative;
  z-index: 1;
  min-width: 0;
  margin-bottom: var(--home-brand-stage-height);
  background: #f8faff;
}

@media (max-width: 900px) {
  .home-reveal-shell {
    --home-sidebar-width: 0px;
  }

  .home-brand-underlay {
    left: 0;
    right: 0;
  }
}

@media (max-width: 700px) {
  .home-brand-underlay {
    left: 0;
    right: 0;
  }
}
</style>
