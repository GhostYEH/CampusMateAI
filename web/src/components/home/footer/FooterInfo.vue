<script setup>
import { onBeforeUnmount, shallowRef } from "vue";
import { RouterLink } from "vue-router";
import UiIcon from "../../UiIcon.vue";

const contactEmail = "y3288365856@gmail.com";
const mailtoHref = `mailto:${contactEmail}?subject=${encodeURIComponent("CampusMate 使用反馈")}`;
const copyFeedback = shallowRef("");
let copyFeedbackTimer = null;

const linkGroups = [
  {
    title: "校园服务",
    links: [
      { label: "我的课程", to: "/courses" },
      { label: "办事大厅", to: "/services" },
      { label: "考试安排", to: "/exams" },
      { label: "通知整理", to: "/notifications" },
    ],
  },
  {
    title: "帮助与社区",
    links: [
      { label: "校园社区", to: "/community" },
      { label: "AI 校园助手", to: "/counselor" },
      { label: "学习陪伴", to: "/study" },
      { label: "个人中心", to: "/profile" },
    ],
  },
];

function finderCell(x, y, originX, originY) {
  const localX = x - originX;
  const localY = y - originY;
  if (localX < 0 || localX > 6 || localY < 0 || localY > 6) return false;
  return localX === 0 || localX === 6 || localY === 0 || localY === 6 || (localX >= 2 && localX <= 4 && localY >= 2 && localY <= 4);
}

function makeQrPattern(seed) {
  const cells = [];
  const size = 21;
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      const inFinder = finderCell(x, y, 0, 0) || finderCell(x, y, 14, 0) || finderCell(x, y, 0, 14);
      const seedValue = seed.charCodeAt((x * 5 + y * 3) % seed.length);
      const dark = inFinder || ((x * 17 + y * 29 + seedValue) % 7 < 3);
      cells.push({ key: `${seed}-${x}-${y}`, dark });
    }
  }
  return cells;
}

const wechatQr = makeQrPattern("wechat-campusmate");
const appQr = makeQrPattern("app-campusmate");

function scrollToTop() {
  const scrollingElement = document.scrollingElement || document.documentElement;
  scrollingElement?.scrollTo({ top: 0, behavior: "smooth" });
}

function setCopyFeedback(message) {
  copyFeedback.value = message;
  if (copyFeedbackTimer) window.clearTimeout(copyFeedbackTimer);
  copyFeedbackTimer = window.setTimeout(() => {
    copyFeedback.value = "";
    copyFeedbackTimer = null;
  }, 1800);
}

function copyWithFallback(text) {
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);
  const copied = document.execCommand("copy");
  textarea.remove();
  return copied;
}

async function copyEmail() {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(contactEmail);
    } else if (!copyWithFallback(contactEmail)) {
      throw new Error("Clipboard fallback failed");
    }
    setCopyFeedback("邮箱已复制");
  } catch {
    try {
      if (!copyWithFallback(contactEmail)) throw new Error("Clipboard fallback failed");
      setCopyFeedback("邮箱已复制");
    } catch {
      setCopyFeedback("复制失败，请手动复制");
    }
  }
}

onBeforeUnmount(() => {
  if (copyFeedbackTimer) window.clearTimeout(copyFeedbackTimer);
});
</script>

<template>
  <footer class="home-footer-info">
    <div class="home-footer-main">
      <section class="home-footer-about" aria-labelledby="footer-brand-title">
        <h2 id="footer-brand-title">CampusMate</h2>
        <p>让校园生活更高效，更有温度。</p>
        <div class="home-footer-socials" aria-label="社交与联系">
          <a :href="mailtoHref" :aria-label="`发送邮件到 ${contactEmail}`"><UiIcon name="PhEnvelopeSimple" :size="17" /></a>
          <a href="/community" aria-label="进入校园社区"><UiIcon name="PhChatsCircle" :size="17" /></a>
        </div>
      </section>

      <nav v-for="group in linkGroups" :key="group.title" class="home-footer-links" :aria-label="group.title">
        <h3>{{ group.title }}</h3>
        <template v-for="link in group.links" :key="link.label">
          <RouterLink v-if="link.to" :to="link.to">{{ link.label }}</RouterLink>
          <a v-else :href="link.href">{{ link.label }}</a>
        </template>
      </nav>

      <section class="home-footer-contact" aria-labelledby="footer-contact-title">
        <h3 id="footer-contact-title">联系我们</h3>
        <p>有建议、问题或合作想法？<br />欢迎通过邮箱联系我们。</p>
        <div class="home-footer-email-field">
          <UiIcon name="PhEnvelopeSimple" :size="16" />
          <a :href="mailtoHref" :aria-label="`联系邮箱 ${contactEmail}`">{{ contactEmail }}</a>
          <button type="button" class="home-footer-copy-icon" aria-label="复制邮箱地址" @click="copyEmail">
            <UiIcon :name="copyFeedback === '邮箱已复制' ? 'PhCheck' : 'PhCopy'" :size="15" />
          </button>
        </div>
        <div class="home-footer-contact-actions">
          <a class="home-footer-mail-button" :href="mailtoHref" :aria-label="`发送邮件到 ${contactEmail}`">
            <UiIcon name="PhPaperPlaneTilt" :size="14" />发送邮件<UiIcon name="PhArrowRight" :size="13" />
          </a>
          <button type="button" class="home-footer-copy-button" aria-label="复制邮箱地址" @click="copyEmail">
            <UiIcon :name="copyFeedback === '邮箱已复制' ? 'PhCheck' : 'PhCopy'" :size="14" />
            {{ copyFeedback || "复制邮箱" }}
          </button>
        </div>
        <span v-if="copyFeedback" class="home-footer-copy-feedback" aria-live="polite">{{ copyFeedback }}</span>
        <small class="home-footer-hours"><strong>工作时间</strong>9:00–18:00</small>
      </section>

      <section class="home-footer-downloads" aria-label="关注与下载">
        <div class="home-footer-qr-card">
          <div class="home-footer-qr" aria-hidden="true">
            <i v-for="cell in wechatQr" :key="cell.key" :class="{ dark: cell.dark }"></i>
          </div>
          <span><strong>关注微信公众号</strong><small>获取最新校园资讯</small></span>
        </div>
        <div class="home-footer-qr-card">
          <div class="home-footer-qr" aria-hidden="true">
            <i v-for="cell in appQr" :key="cell.key" :class="{ dark: cell.dark }"></i>
          </div>
          <span><strong>下载移动端 App</strong><small>随时随地掌握校园动态</small></span>
        </div>
      </section>
    </div>

    <div class="home-footer-bottom">
      <span>CampusMate · 连接每一段校园日常</span>
      <button type="button" class="home-footer-top" @click="scrollToTop">
        <UiIcon name="PhArrowRight" :size="15" class="home-footer-top-icon" />返回顶部
      </button>
    </div>
  </footer>
</template>

<style scoped>
.home-footer-info {
  --home-footer-bleed-width: calc(100vw - var(--home-sidebar-width, 282px));
  display: grid;
  gap: 22px;
  width: var(--home-footer-bleed-width);
  margin-left: calc((100% - var(--home-footer-bleed-width)) / 2);
  padding: 30px clamp(28px, 3vw, 48px) 17px;
  border-top: 1px solid #e9edf5;
  border-bottom: 0;
  border-radius: 0;
  background: #fff;
  color: #263a5a;
}

.home-footer-main {
  display: grid;
  grid-template-columns: minmax(194px, 1.2fr) repeat(2, minmax(118px, .7fr)) minmax(244px, 1.25fr) minmax(274px, 1.45fr);
  gap: 26px;
  align-items: start;
}

.home-footer-about,
.home-footer-links,
.home-footer-contact,
.home-footer-downloads {
  min-width: 0;
}

.home-footer-about h2 {
  margin: 0;
  color: #355cf0;
  font-size: 24px;
  font-weight: 850;
  letter-spacing: -.04em;
}

.home-footer-about p {
  margin: 7px 0 18px;
  color: #8390a8;
  font-size: 11px;
  line-height: 1.6;
}

.home-footer-socials {
  display: flex;
  gap: 8px;
}

.home-footer-socials a {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid #e2e7f1;
  border-radius: 50%;
  color: #657594;
  transition: border-color .18s ease, color .18s ease, background .18s ease, transform .18s ease;
}

.home-footer-socials a:hover {
  border-color: #c6d0f5;
  background: #f5f7ff;
  color: #4165ed;
  transform: translateY(-2px);
}

.home-footer-links {
  display: grid;
  align-content: start;
  gap: 9px;
}

.home-footer-links h3 {
  margin: 0 0 4px;
  color: #2e4263;
  font-size: 12px;
}

.home-footer-links a {
  overflow: hidden;
  color: #8290a8;
  font-size: 10px;
  text-overflow: ellipsis;
  text-decoration: none;
  white-space: nowrap;
  transition: color .18s ease;
}

.home-footer-links a:hover {
  color: #4165ed;
}

.home-footer-contact {
  display: grid;
  align-content: start;
  gap: 9px;
}

.home-footer-contact h3 {
  margin: 0 0 1px;
  color: #2e4263;
  font-size: 12px;
}

.home-footer-contact > p {
  margin: 0;
  color: #8290a8;
  font-size: 10px;
  line-height: 1.55;
}

.home-footer-email-field {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) 24px;
  align-items: center;
  gap: 7px;
  min-width: 0;
  padding: 8px 9px;
  border: 1px solid rgba(91, 92, 255, .14);
  border-radius: 12px;
  background: rgba(91, 92, 255, .06);
  color: #6573d7;
  transition: border-color .18s ease, background .18s ease;
}

.home-footer-email-field:hover,
.home-footer-email-field:focus-within {
  border-color: rgba(91, 92, 255, .32);
  background: rgba(91, 92, 255, .1);
}

.home-footer-email-field > a {
  min-width: 0;
  overflow-wrap: anywhere;
  color: #4358cf;
  font-size: 10px;
  line-height: 1.4;
  text-decoration: none;
}

.home-footer-email-field > a:hover {
  text-decoration: underline;
}

.home-footer-copy-icon {
  width: 24px;
  height: 24px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 7px;
  background: rgba(255, 255, 255, .72);
  color: #6878d9;
}

.home-footer-copy-icon:hover {
  background: #fff;
  color: #4358cf;
}

.home-footer-contact-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.home-footer-mail-button,
.home-footer-copy-button {
  min-height: 29px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 0 9px;
  border: 1px solid #e1e6f3;
  border-radius: 8px;
  background: #fff;
  color: #647394;
  font-size: 9px;
  text-decoration: none;
  transition: border-color .18s ease, background .18s ease, color .18s ease;
}

.home-footer-mail-button {
  border-color: #cfd6ff;
  background: #f4f5ff;
  color: #4c5ee0;
}

.home-footer-mail-button:hover,
.home-footer-copy-button:hover {
  border-color: #aeb9f5;
  background: #f7f8ff;
  color: #4358cf;
}

.home-footer-copy-feedback {
  color: #4f9a78;
  font-size: 9px;
}

.home-footer-hours {
  display: flex;
  gap: 6px;
  color: #9aa5ba;
  font-size: 9px;
}

.home-footer-hours strong {
  color: #6d7d9d;
  font-weight: 650;
}

.home-footer-downloads {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.home-footer-qr-card {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  align-items: center;
  gap: 10px;
  min-width: 0;
  padding: 10px;
  border: 1px solid #e6eaf2;
  border-radius: 13px;
  background: linear-gradient(145deg, #fbfcff, #fff);
}

.home-footer-qr {
  width: 72px;
  height: 72px;
  display: grid;
  grid-template-columns: repeat(21, 1fr);
  grid-template-rows: repeat(21, 1fr);
  gap: 1px;
  padding: 4px;
  border: 1px solid #e6eaf1;
  background: #fff;
}

.home-footer-qr i {
  display: block;
  background: transparent;
}

.home-footer-qr i.dark {
  background: #263b5b;
}

.home-footer-qr-card > span {
  display: grid;
  gap: 5px;
  min-width: 0;
}

.home-footer-qr-card strong {
  color: #354a6c;
  font-size: 10px;
  line-height: 1.35;
}

.home-footer-qr-card small {
  color: #8d99ad;
  font-size: 8px;
  line-height: 1.45;
}

.home-footer-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  padding-top: 14px;
  border-top: 1px solid #edf0f5;
  color: #a0aabd;
  font-size: 10px;
}

.home-footer-top {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 0;
  border: 0;
  background: transparent;
  color: #6f80a0;
  font-size: 10px;
  cursor: pointer;
  transition: color .18s ease;
}

.home-footer-top:hover {
  color: #4165ed;
}

.home-footer-top-icon {
  transform: rotate(-90deg);
}

.home-footer-socials a:focus-visible,
.home-footer-links a:focus-visible,
.home-footer-contact a:focus-visible,
.home-footer-contact button:focus-visible,
.home-footer-top:focus-visible {
  outline: 3px solid #9aaeff;
  outline-offset: 3px;
}

@media (max-width: 1280px) {
  .home-footer-main {
    grid-template-columns: minmax(184px, 1.2fr) repeat(2, minmax(106px, .7fr)) minmax(220px, 1.2fr);
  }

  .home-footer-downloads {
    grid-column: 1 / -1;
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 760px) {
  .home-footer-info {
    padding: 24px 18px 16px;
  }

  .home-footer-main {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 24px 18px;
  }

  .home-footer-about {
    grid-column: 1 / -1;
  }

  .home-footer-contact {
    grid-column: 1 / -1;
  }

  .home-footer-downloads {
    grid-template-columns: 1fr;
    grid-column: 1 / -1;
  }
}

@media (max-width: 420px) {
  .home-footer-bottom {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .home-footer-downloads {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .home-footer-socials a,
  .home-footer-links a,
  .home-footer-contact a,
  .home-footer-contact button,
  .home-footer-top {
    transition: none;
  }

  .home-footer-socials a:hover {
    transform: none;
  }
}
</style>
