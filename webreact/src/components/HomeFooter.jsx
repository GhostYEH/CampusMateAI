import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import QRCode from "qrcode";
import { Icon } from "./Icon.jsx";
import ParticleText from "./ParticleText.jsx";

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
  return <section className="home-footer-brand" aria-labelledby="react-footer-brand-effect-title">
    <h2 id="react-footer-brand-effect-title" className="home-visually-hidden">CampusMate 互动品牌区</h2>
    <ParticleText
      text="CAMPUSMATE"
      particleSize={2}
      density={4}
      color="#f8fcff"
      highlightColor="#c8d8ff"
      scatter={0}
      gatherDuration={1}
      stagger={0}
      pointerRepel={40}
      repelRadius={70}
      idleDrift={0.7}
      animateOnMount={false}
      trigger="hover"
      fontSize="clamp(4.5rem, 16vw, 11rem)"
      fontWeight={800}
      fontFamily="inherit"
      glow
    />
    <span className="home-footer-brand-caption">MOVE THROUGH CAMPUSMATE</span>
  </section>;
}
export default function HomeFooter({ children, fixedBrand = false }) {
  return <section className={`home-footer${fixedBrand ? " home-footer-fixed-brand" : ""}`} aria-label="CampusMate 首页内容与品牌页脚">
    {fixedBrand && <div className="home-brand-underlay"><HomeBrandCanvas /></div>}
    <div className="home-foreground">
      {children}
      <FooterInfo />
    </div>
    {!fixedBrand && <HomeBrandCanvas />}
  </section>;
}
