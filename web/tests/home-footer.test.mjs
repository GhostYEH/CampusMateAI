import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

test("both student home modes keep the footer foreground inside the page gutter", async () => {
  const [entry, classicHome, gamifiedHome, footer, info, brand] = await Promise.all([
    readFile(path.join(webRoot, "src/views/student/StudentHomeView.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/home/ClassicStudentHome.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/home/gamified/GamifiedStudentHome.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/home/footer/HomeFooter.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/home/footer/FooterInfo.vue"), "utf8"),
    readFile(path.join(webRoot, "src/components/home/footer/InteractiveBrand.vue"), "utf8"),
  ]);

  assert.match(classicHome, /<HomeFooter(?:\s[^>]*)?>/);
  assert.match(classicHome, /<\/HomeFooter>/);
  assert.match(gamifiedHome, /<HomeFooter(?:\s[^>]*)?>/);
  assert.match(gamifiedHome, /<\/HomeFooter>/);
  assert.doesNotMatch(entry, /student-home page-enter/);
  assert.match(footer, /FooterInfo/);
  assert.match(footer, /InteractiveBrand/);
  assert.match(footer, /home-brand-underlay/);
  assert.match(footer, /home-foreground/);
  assert.match(footer, /margin-bottom/);
  assert.match(footer, /\.home-foreground[\s\S]*width: 100%/);
  assert.match(footer, /\.home-foreground[\s\S]*margin-left: 0/);
  assert.match(footer, /\.home-reveal-shell::before,[\s\S]*\.home-reveal-shell::after/);
  assert.match(footer, /width: var\(--student-page-gutter, 36px\)/);
  assert.match(footer, /background: #f8faff/);
  assert.match(footer, /left: var\(--home-sidebar-width\)/);
  assert.match(footer, /right: 0/);
  assert.match(info, /100vw - var\(--home-sidebar-width/);
  assert.match(info, /clamp\(28px, 3vw, 48px\)/);
  assert.match(info, /CampusMate/);
  assert.match(info, /关注微信公众号/);
  assert.match(info, /下载移动端 App/);
  assert.match(info, /返回顶部/);
  assert.match(info, /\/courses/);
  assert.match(info, /\/community/);
  assert.match(info, /scrollTo\(/);
  assert.match(info, /y3288365856@gmail\.com/);
  assert.match(info, /mailtoHref/);
  assert.doesNotMatch(info, /support@campusmate\.cn|400-034-7888/);
  assert.match(info, /navigator\.clipboard/);
  assert.match(info, /execCommand\("copy"\)/);
  assert.match(info, /邮箱已复制/);
  assert.match(info, /复制邮箱地址/);
  assert.match(brand, /canvas/);
  assert.match(brand, /gsap\.ticker\.add/);
  assert.match(brand, /gsap\.ticker\.remove/);
  assert.doesNotMatch(brand, /requestAnimationFrame/);
  assert.match(brand, /ResizeObserver/);
  assert.match(brand, /devicePixelRatio/);
  assert.match(brand, /pointerVelocityX/);
  assert.match(brand, /pointerVelocityY/);
  assert.match(brand, /onBeforeUnmount/);
  assert.match(brand, /prefers-reduced-motion/);
  assert.match(brand, /coarse/);
  assert.match(brand, /14, 48/);
  assert.doesNotMatch(brand, /opacity:\s*0/);
  assert.doesNotMatch(brand, /translateY\(32px\)/);
});
