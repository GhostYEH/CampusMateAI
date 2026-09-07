import { Link, useLocation } from "react-router-dom";
import { Icon } from "../Icon.jsx";
import { isSummerNavActive, SUMMER_NAV_LINKS } from "../../features/study/summerNav.js";

export default function SummerNavDock({ sceneAudio }) {
  const { pathname } = useLocation();
  const audio = sceneAudio || { enabled: false, toggle: () => {} };
  return <nav className="study-summer-dock" aria-label="学习陪伴导航"><div className="study-summer-dock__inner"><Link to="/study" className={`study-summer-dock__brand${pathname === "/study" ? " is-current" : ""}`}><span className="study-summer-dock__logo"><Icon name="PhTree" size={13} weight="fill" /></span><span>学习陪伴</span></Link><div className="study-summer-dock__links">{SUMMER_NAV_LINKS.map((item) => <Link key={item.to} to={item.to} className={isSummerNavActive(pathname, item.to) ? "is-active" : ""}>{item.label}</Link>)}</div><div className="study-summer-dock__tools"><button type="button" className={audio.enabled ? "is-active" : ""} aria-pressed={audio.enabled} onClick={audio.toggle}><Icon name="PhWaveform" size={15} /><span>场景音</span></button></div></div></nav>;
}
