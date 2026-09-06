import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import { Icon } from "./Icon.jsx";

const contactEmail = "y3288365856@gmail.com";
const mailtoHref = `mailto:${contactEmail}?subject=${encodeURIComponent("CampusMate 使用反馈")}`;


const linkGroups = [
  {
    title: "校园服务",
    links: [["我的课程", "/courses"], ["办事大厅", "/services"], ["考试安排", "/exams"], ["通知整理", "/notifications"]],
  },
  {
    title: "帮助与社区",
    links: [["校园社区", "/community"], ["AI 校园助手", "/counselor"], ["学习陪伴", "/study"], ["个人中心", "/profile"]],
  },
];

function QrCard({ title, detail, value }) {
  const [source, setSource] = useState("");

  useEffect(() => {
    let active = true;
    QRCode.toDataURL(value, {
      width: 160,
      margin: 1,
      color: { dark: "#263b5b", light: "#ffffff" },
    }).then((dataUrl) => active && setSource(dataUrl)).catch(() => active && setSource(""));
    return () => { active = false; };
  }, [value]);

  return <article className="home-footer-qr-card">
    <div className="home-footer-qr" aria-hidden="true">
      {source ? <img src={source} alt="" /> : <Icon name="PhQrCode" size={58} />}
    </div>
    <span><strong>{title}</strong><small>{detail}</small></span>
  </article>;
}

function copyFallback(value) {
  const textarea = document.createElement("textarea");
  textarea.value = value;
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

function FooterInfo() {
  const [copyFeedback, setCopyFeedback] = useState("");

  async function copyEmail() {
    try {
      if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(contactEmail);
      else if (!copyFallback(contactEmail)) throw new Error("Clipboard fallback failed");
      setCopyFeedback("邮箱已复制");
    } catch {
      try {
        if (!copyFallback(contactEmail)) throw new Error("Clipboard fallback failed");
        setCopyFeedback("邮箱已复制");
      } catch {
        setCopyFeedback("复制失败，请手动复制");
      }
    }
    window.setTimeout(() => setCopyFeedback(""), 1800);
  }

  function scrollToTop() {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return <footer className="home-footer-info">
    <div className="home-footer-main">
      <section className="home-footer-about" aria-labelledby="react-footer-brand-title">
        <h2 id="react-footer-brand-title">CampusMate</h2>
        <p>让校园生活更高效，更有温度。</p>
        <div className="home-footer-socials" aria-label="社交与联系">
          <a href={mailtoHref} aria-label={`发送邮件到 ${contactEmail}`}><Icon name="PhEnvelopeSimple" size={17} /></a>
          <Link to="/community" aria-label="进入校园社区"><Icon name="PhChatsCircle" size={17} /></Link>
        </div>
      </section>

      {linkGroups.map((group) => <nav key={group.title} className="home-footer-links" aria-label={group.title}>
        <h3>{group.title}</h3>
        {group.links.map(([label, to]) => <Link key={to} to={to}>{label}</Link>)}
      </nav>)}

      <section className="home-footer-contact" aria-labelledby="react-footer-contact-title">
        <h3 id="react-footer-contact-title">联系我们</h3>
        <p>有建议、问题或合作想法？<br />欢迎通过邮箱联系我们。</p>
        <div className="home-footer-email-field">
          <Icon name="PhEnvelopeSimple" size={16} />
          <a href={mailtoHref} aria-label={`联系邮箱 ${contactEmail}`}>{contactEmail}</a>
          <button type="button" className="home-footer-copy-icon" aria-label="复制邮箱地址" onClick={copyEmail}>
            <Icon name={copyFeedback === "邮箱已复制" ? "PhCheck" : "PhCopy"} size={15} />
          </button>
        </div>
        <div className="home-footer-contact-actions">
          <a className="home-footer-mail-button" href={mailtoHref} aria-label={`发送邮件到 ${contactEmail}`}><Icon name="PhPaperPlaneRight" size={14} />发送邮件<Icon name="PhArrowRight" size={13} /></a>
          <button type="button" className="home-footer-copy-button" onClick={copyEmail}><Icon name="PhCopy" size={14} />{copyFeedback || "复制邮箱"}</button>
        </div>
        {copyFeedback && <span className="home-footer-copy-feedback" aria-live="polite">{copyFeedback}</span>}
        <small className="home-footer-hours"><strong>工作时间</strong>9:00–18:00</small>
      </section>

      <section className="home-footer-downloads" aria-label="关注与下载">
        <QrCard title="关注微信公众号" detail="获取最新校园资讯" value={`${origin}/community`} />
        <QrCard title="下载移动端 App" detail="随时随地掌握校园动态" value={`${origin}/app`} />
      </section>
    </div>
    <div className="home-footer-bottom">
      <span>CampusMate · 连接每一段校园日常</span>
      <button type="button" className="home-footer-top" onClick={scrollToTop}><Icon name="PhArrowRight" size={15} className="home-footer-top-icon" />返回顶部</button>
    </div>
  </footer>;
}

function HomeBrandCanvas() {
  const sectionRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const section = sectionRef.current;
    const canvas = canvasRef.current;
    const context = canvas?.getContext("2d");
    if (!section || !canvas || !context) return undefined;

    const sourceCanvas = document.createElement("canvas");
    const sourceContext = sourceCanvas.getContext("2d");
    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const coarseQuery = window.matchMedia("(pointer: coarse)");
    let width = 1;
    let height = 1;
    let pixelRatio = 1;
    let sliceHeight = 16;
    let frameId = 0;
    let pointerActive = false;
    let lastPoint = null;
    let targetAmplitude = 0;
    let currentAmplitude = 0;
    let targetX = 0;
    let targetY = 0;
    let currentX = 0;
    let currentY = 0;

    const isStatic = () => motionQuery.matches || coarseQuery.matches;
    const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

    function paintSource() {
      sourceContext.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      sourceContext.clearRect(0, 0, width, height);
      let fontSize = Math.min(height * 0.84, width / 7.1);
      sourceContext.font = `900 ${fontSize}px Arial Black, Arial, sans-serif`;
      const metrics = sourceContext.measureText("CAMPUSMATE");
      if (metrics.width > width * 0.94) fontSize *= width * 0.94 / metrics.width;
      sourceContext.font = `900 ${fontSize}px Arial Black, Arial, sans-serif`;
      const fitted = sourceContext.measureText("CAMPUSMATE");
      const ascent = fitted.actualBoundingBoxAscent || fontSize * 0.72;
      const descent = fitted.actualBoundingBoxDescent || fontSize * 0.18;
      sourceContext.fillStyle = "rgba(255, 255, 255, .98)";
      sourceContext.textBaseline = "alphabetic";
      sourceContext.fillText("CAMPUSMATE", (width - fitted.width) / 2, height / 2 + (ascent - descent) / 2);
    }

    function draw() {
      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, width, height);
      context.drawImage(sourceCanvas, 0, 0, sourceCanvas.width, sourceCanvas.height, 0, 0, width, height);
      if (isStatic() || !pointerActive || currentAmplitude < 0.01) return;
      const radiusX = clamp(width * 0.2, 150, 290);
      const radiusY = clamp(height * 0.62, 70, 155);
      const count = Math.ceil(height / sliceHeight);
      for (let index = 0; index < count; index += 1) {
        const y = index * sliceHeight;
        const heightOfSlice = Math.min(sliceHeight, height - y);
        const verticalInfluence = Math.exp(-((Math.abs(y + heightOfSlice / 2 - currentY) ** 2) / (2 * radiusY ** 2)));
        const horizontalInfluence = Math.exp(-((Math.abs(currentX - width / 2) ** 2) / (2 * radiusX ** 2)));
        const influence = verticalInfluence * (0.65 + horizontalInfluence * 0.35);
        if (influence < 0.015) continue;
        const direction = index % 2 === 0 ? 1 : -1;
        const offset = direction * currentAmplitude * 72 * influence;
        context.save();
        context.beginPath();
        context.rect(currentX - radiusX, y, radiusX * 2, heightOfSlice);
        context.clip();
        context.drawImage(sourceCanvas, 0, y * pixelRatio, sourceCanvas.width, heightOfSlice * pixelRatio, offset, y, width, heightOfSlice);
        context.restore();
      }
    }

    function animate() {
      frameId = 0;
      currentX += (targetX - currentX) * 0.14;
      currentY += (targetY - currentY) * 0.14;
      currentAmplitude += (targetAmplitude - currentAmplitude) * 0.12;
      targetAmplitude *= pointerActive ? 0.93 : 0.76;
      draw();
      if (pointerActive || currentAmplitude > 0.01 || targetAmplitude > 0.01) frameId = window.requestAnimationFrame(animate);
    }

    function schedule() {
      if (!frameId) frameId = window.requestAnimationFrame(animate);
    }

    function resize() {
      const bounds = section.getBoundingClientRect();
      width = Math.max(1, Math.round(bounds.width));
      height = Math.max(1, Math.round(bounds.height));
      pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
      sliceHeight = clamp(Math.round(height / 11), 14, 48);
      canvas.width = Math.round(width * pixelRatio);
      canvas.height = Math.round(height * pixelRatio);
      sourceCanvas.width = canvas.width;
      sourceCanvas.height = canvas.height;
      targetX = currentX = width / 2;
      targetY = currentY = height / 2;
      paintSource();
      draw();
    }

    function handlePointerMove(event) {
      if (isStatic()) return;
      const bounds = canvas.getBoundingClientRect();
      const x = clamp(event.clientX - bounds.left, 0, width);
      const y = clamp(event.clientY - bounds.top, 0, height);
      const velocity = lastPoint ? Math.hypot(x - lastPoint.x, y - lastPoint.y) : 0;
      targetX = x;
      targetY = y;
      targetAmplitude = clamp(velocity / 55, 0, 1.8);
      lastPoint = { x, y };
      pointerActive = true;
      schedule();
    }

    function handlePointerLeave() {
      pointerActive = false;
      lastPoint = null;
      targetAmplitude = 0;
      schedule();
    }

    function updateMotionMode() {
      if (isStatic()) {
        pointerActive = false;
        targetAmplitude = 0;
        currentAmplitude = 0;
        if (frameId) window.cancelAnimationFrame(frameId);
        frameId = 0;
        draw();
      }
    }

    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(section);
    section.addEventListener("pointermove", handlePointerMove);
    section.addEventListener("pointerleave", handlePointerLeave);
    motionQuery.addEventListener("change", updateMotionMode);
    coarseQuery.addEventListener("change", updateMotionMode);
    return () => {
      observer.disconnect();
      section.removeEventListener("pointermove", handlePointerMove);
      section.removeEventListener("pointerleave", handlePointerLeave);
      motionQuery.removeEventListener("change", updateMotionMode);
      coarseQuery.removeEventListener("change", updateMotionMode);
      if (frameId) window.cancelAnimationFrame(frameId);
    };
  }, []);

  return <section ref={sectionRef} className="home-footer-brand" aria-labelledby="react-footer-brand-effect-title">
    <h2 id="react-footer-brand-effect-title" className="home-visually-hidden">CampusMate 互动品牌区</h2>
    <canvas ref={canvasRef} role="img" aria-label="CAMPUSMATE">CAMPUSMATE</canvas>
    <span>MOVE THROUGH CAMPUSMATE</span>
  </section>;
}

export default function HomeFooter({ children }) {
  return <section className="home-footer" aria-label="CampusMate 首页内容与品牌页脚">
    <div className="home-foreground">{children}</div>
    <FooterInfo />
    <HomeBrandCanvas />
  </section>;
}
