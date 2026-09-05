import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import QRCode from "qrcode";
import { qrCreate, qrExchange, qrStatus } from "../data/api.js";
import { qrStatusState } from "../data/alignment.js";
import { useApp } from "../app/AppContext.jsx";
import { Icon } from "../components/Icon.jsx";
import GlassSurface from "../components/GlassSurface.jsx";
import LiquidChrome from "../components/LiquidChrome.jsx";
import TiltedCard from "../components/TiltedCard.jsx";

export default function LoginPage() {
  const { session, login, applyQrLoginResult, tryTrustedLogin } = useApp();
  const navigate = useNavigate();
  const [mode, setMode] = useState("account");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);
  const [qr, setQr] = useState({ state: "idle", image: "", session: null, error: "" });
  const pollRef = useRef();

  function stopQrPolling() {
    clearInterval(pollRef.current);
    pollRef.current = undefined;
  }

  useEffect(() => {
    let active = true;
    if (session) {
      navigate("/home", { replace: true });
      return undefined;
    }
    tryTrustedLogin().then((ok) => {
      if (active && ok) navigate("/home", { replace: true });
      if (active) setChecking(false);
    });
    return () => {
      active = false;
      stopQrPolling();
    };
  }, [session, navigate, tryTrustedLogin]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username.trim(), password);
      navigate("/home", { replace: true });
    } catch (err) {
      setError(err.message || "登录失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  async function generateQr() {
    stopQrPolling();
    setQr({ state: "generating", image: "", session: null, error: "" });
    try {
      const data = await qrCreate();
      const image = await QRCode.toDataURL(data.qr_payload, {
        width: 220,
        margin: 1,
        color: { dark: "#17232d", light: "#fff" },
      });
      const sessionData = { session_id: data.session_id, browser_token: data.browser_token };
      setQr({ state: "pending", image, session: sessionData, error: "" });
      pollRef.current = setInterval(async () => {
        try {
          const status = await qrStatus(sessionData.session_id, sessionData.browser_token);
          const next = qrStatusState(status.status);
          if (next.state === "confirmed") {
            stopQrPolling();
            setQr((current) => ({ ...current, state: "confirmed" }));
            try {
              const tokenPair = await qrExchange(sessionData.session_id, sessionData.browser_token);
              applyQrLoginResult(tokenPair);
              navigate("/home", { replace: true });
            } catch (exchangeError) {
              setQr((current) => ({ ...current, state: "error", error: exchangeError?.response?.data?.detail || exchangeError?.message || "二维码登录失败，请重新生成" }));
            }
            return;
          }
          if (next.state !== "pending") {
            if (["expired", "cancelled", "error"].includes(next.state)) stopQrPolling();
            setQr((current) => ({ ...current, ...next }));
          }
        } catch {
          // Keep polling through transient status errors.
        }
      }, 1000);
    } catch (err) {
      setQr({ state: "error", image: "", session: null, error: err.message || "生成二维码失败" });
    }
  }

  if (checking) {
    return <main className="login-page login-checking"><div className="login-panel"><span className="loading-orb" /><p>正在检查登录状态…</p></div></main>;
  }

  return (
    <main className="login-page">
      <div className="login-media" aria-hidden="true"><video src="/assets/login-campus.mp4" autoPlay muted loop playsInline /></div>
      <div className="login-shade" />
      <section className="login-story">
        <div className="login-brand"><span className="brand-mark"><Icon name="PhGraduationCap" size={24} weight="fill" /></span><span><strong>CampusMate AI</strong><small>校园信息中枢</small></span></div>
        <div className="login-copy"><span className="eyebrow">你的校园事务工作台</span><h1>把今天的校园生活<br />理清楚。</h1><p>通知、课程、任务和 AI 导员，都在一个清晰的入口。</p></div>
        <div className="login-feature"><span><Icon name="PhBell" />通知智能整理</span><span><Icon name="PhCheckSquare" />任务协同管理</span><span><Icon name="PhRobot" />AI 导员陪伴</span></div>
      </section>

      <TiltedCard className="login-panel-tilted" containerHeight="auto" containerWidth="calc(100% - 64px)" imageHeight="auto" imageWidth="100%" rotateAmplitude={20} scaleOnHover={1.2} showMobileWarning={false} showTooltip={false}>
        <section className="login-panel">
          <LiquidChrome className="login-panel-liquid" baseColor={[0.1, 0.1, 0.1]} speed={1} amplitude={0.6} interactive={true} aria-hidden="true" />
          <div className="login-panel-content">
            <div className="login-panel-head"><span className="eyebrow">欢迎回来</span><h2>登录 CampusMate</h2><p>查看校园通知、课程与个人待办</p></div>
            <GlassSurface className="login-mode-glass" width="100%" height={48} borderRadius={12} brightness={70} opacity={0.84} blur={8} displace={15} backgroundOpacity={0.16} saturation={1.25} distortionScale={-150} redOffset={5} greenOffset={15} blueOffset={25} mixBlendMode="screen">
              <div className="login-mode-switch">
                <button className={mode === "account" ? "active" : ""} onClick={() => { stopQrPolling(); setQr({ state: "idle", image: "", session: null, error: "" }); setMode("account"); }}><Icon name="PhUser" />账号登录</button>
                <button className={mode === "qr" ? "active" : ""} onClick={() => { setMode("qr"); if (qr.state === "idle") generateQr(); }}><Icon name="PhQrCode" />扫码登录</button>
              </div>
            </GlassSurface>
            {mode === "account" ? (
              <form onSubmit={submit} className="login-form">
                <label>学号或用户名<GlassSurface className="login-input-glass" width="100%" height={44} borderRadius={10} brightness={82} opacity={0.88} blur={7} displace={10} backgroundOpacity={0.2} saturation={1.2} distortionScale={-105} redOffset={3} greenOffset={10} blueOffset={17} mixBlendMode="screen"><div className="input-wrap"><Icon name="PhUser" /><input required value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" placeholder="请输入学号或用户名" /></div></GlassSurface></label>
                <label>密码<GlassSurface className="login-input-glass" width="100%" height={44} borderRadius={10} brightness={82} opacity={0.88} blur={7} displace={10} backgroundOpacity={0.2} saturation={1.2} distortionScale={-105} redOffset={3} greenOffset={10} blueOffset={17} mixBlendMode="screen"><div className="input-wrap"><Icon name="PhLock" /><input required value={password} onChange={(event) => setPassword(event.target.value)} type={showPassword ? "text" : "password"} autoComplete="current-password" placeholder="请输入密码" /><button type="button" className="icon-button" aria-label={showPassword ? "隐藏密码" : "显示密码"} onClick={() => setShowPassword((value) => !value)}><Icon name={showPassword ? "PhEyeSlash" : "PhEye"} /></button></div></GlassSurface></label>
                {error && <div className="alert-error" role="alert"><Icon name="PhWarningCircle" />{error}</div>}
                <GlassSurface className="login-button-glass" width="100%" height={46} borderRadius={11} brightness={62} opacity={0.9} blur={7} displace={12} backgroundOpacity={0.12} saturation={1.2} distortionScale={-120} redOffset={4} greenOffset={12} blueOffset={20} mixBlendMode="screen"><button className="button button-primary login-submit" disabled={loading}>{loading ? "正在登录…" : "登录"}{!loading && <Icon name="PhArrowRight" />}</button></GlassSurface>
              </form>
            ) : (
              <div className="qr-login-zone"><div className="qr-frame">
                {qr.image && <img className={qr.state === "scanned" || qr.state === "confirmed" ? "dim" : ""} src={qr.image} alt="CampusMate 登录二维码" />}
                {["generating", "confirmed"].includes(qr.state) && <div className="qr-overlay"><span className="loading-orb" /><p>{qr.state === "confirmed" ? "正在登录…" : "正在生成二维码…"}</p></div>}
                {qr.state === "scanned" && <div className="qr-overlay qr-ok"><Icon name="PhCheckCircle" size={42} weight="fill" /><p>扫描成功</p><small>请在手机上确认登录</small></div>}
                {["expired", "cancelled", "error"].includes(qr.state) && <div className="qr-overlay qr-warn"><Icon name={qr.state === "error" ? "PhWarningCircle" : "PhClock"} size={38} /><p>{qr.error || (qr.state === "expired" ? "二维码已过期" : "已取消本次登录")}</p><button className="button button-secondary" onClick={generateQr}><Icon name="PhArrowClockwise" />重新生成</button></div>}
              </div><p className="qr-hint">{qr.state === "scanned" ? "请在手机上确认登录" : qr.state === "confirmed" ? "正在登录，请稍候…" : "打开 CampusMate 手机端，在「我的」右上角点击扫一扫"}</p></div>
            )}
            <div className="login-foot-actions">请使用学校统一身份账号登录</div>
          </div>
        </section>
      </TiltedCard>
    </main>
  );
}
