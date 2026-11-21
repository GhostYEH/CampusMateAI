import "../../styles/magicclass-rewards.css";
import React from "react";
import { BookOpen, Bolt, Check, ChevronDown, Flag, Flame, Lock, Map, Route, Star, Trophy, X } from "lucide-react";

import { ACHIEVEMENTS } from "../../features/magicclass/rewardsModel.js";
import { cn } from "../../magicclass/utils/cn.js";

const ICONS = { book: BookOpen, route: Route, flag: Flag, flame: Flame, bolt: Bolt, star: Star };

/**
 * 课堂游戏化 HUD：等级、XP、连击、关卡地图与成就。
 *
 * 只展示**真实发生过**的进度（来自 rewardsModel 的本地结算），不做"预计得分"
 * 之类的装饰。桌面端 `variant="header"` 常驻头栏，成为课堂的冒险状态条；
 * 手机端 `variant="overlay"` 仍是画布角上一枚可展开的紧凑徽章。
 */
export default function ClassroomGameHud({
  level,
  combo,
  bestCombo,
  achievements = [],
  map = [],
  total = 0,
  unlocked = [],
  onJump,
  onDismiss,
  variant = "overlay",
}) {
  const [open, setOpen] = React.useState(false);
  const earned = new Set(achievements);
  const done = map.filter((item) => item.visited).length;
  const latest = unlocked[unlocked.length - 1] || null;
  const isHeader = variant === "header";

  // 真实 XP 增量与升级都用一次短动画反馈；不改变结算，只把结算结果说出来。
  const previousXp = React.useRef(level.xp);
  const previousLevel = React.useRef(level.level);
  const [gain, setGain] = React.useState(0);
  const [levelUp, setLevelUp] = React.useState("");
  React.useEffect(() => {
    const delta = level.xp - previousXp.current;
    previousXp.current = level.xp;
    if (delta > 0) setGain(delta);
  }, [level.xp]);
  React.useEffect(() => {
    if (!gain) return undefined;
    const timer = window.setTimeout(() => setGain(0), 1300);
    return () => window.clearTimeout(timer);
  }, [gain]);
  React.useEffect(() => {
    if (level.level > previousLevel.current) {
      setLevelUp(`LEVEL ${level.level}`);
      previousLevel.current = level.level;
    }
  }, [level.level]);
  React.useEffect(() => {
    if (!levelUp) return undefined;
    const timer = window.setTimeout(() => setLevelUp(""), 1800);
    return () => window.clearTimeout(timer);
  }, [levelUp]);

  return <div className={cn("cr-hud", isHeader && "cr-hud--header")} data-open={open ? "true" : "false"} data-variant={variant}>
    <button
      type="button"
      className="cr-hud__badge"
      onClick={() => setOpen((value) => !value)}
      aria-expanded={open}
      aria-label={open ? "收起学习进度" : "展开学习进度"}
    >
      <span className="cr-hud__level">Lv.{level.level}</span>
      {isHeader && <span className="cr-hud__rank">冒险者</span>}
      <span className="cr-hud__xp" aria-hidden="true">
        <span style={{ width: `${Math.round(level.progress * 100)}%` }} />
      </span>
      <span className="cr-hud__xp-text">{level.inLevel}/{100}</span>
      {combo > 1 && <span className="cr-hud__combo" title={`连续答对 ${combo} 次`}>×{combo}</span>}
      <ChevronDown className="cr-hud__chevron" size={14} />
    </button>

    {isHeader && <div className="cr-hud__route" aria-label={`关卡进度 ${done}/${total || map.length}`}>
      {map.map((item, index) => <button
        key={item.id}
        type="button"
        className={cn("cr-hud__pip", item.visited && "is-done", item.current && "is-current")}
        onClick={() => onJump?.(item.id)}
        title={`${index + 1}. ${item.title}`}
        aria-label={`跳到第 ${index + 1} 关：${item.title}`}
      >
        {index + 1}
      </button>)}
      <span className="cr-hud__route-count">{done}/{total || map.length}</span>
    </div>}

    {gain > 0 && <span className="cr-hud__gain" aria-live="polite">+{gain} XP</span>}
    {levelUp && <span className="cr-hud__levelup" aria-live="polite">{levelUp}</span>}

    {latest && <button
      type="button"
      className="cr-hud__toast"
      onClick={() => onDismiss?.(latest)}
      title="点击关闭"
    >
      解锁「{ACHIEVEMENTS.find((item) => item.id === latest)?.label || latest}」
      <X size={12} />
    </button>}

    {open && <div className="cr-hud__panel" role="dialog" aria-label="学习进度">
      <header className="cr-hud__panel-head">
        <div>
          <strong>{level.level} 级</strong>
          <span>{level.xp} XP · 再 {level.toNext} XP 升级</span>
        </div>
        <button type="button" className="cr-hud__close" onClick={() => setOpen(false)} aria-label="关闭学习进度">
          <X size={14} />
        </button>
      </header>

      <section className="cr-hud__section">
        <h3><Map size={14} /> 关卡地图 <small>{done}/{total || map.length} 页</small></h3>
        <div className="cr-hud__map">
          {map.map((item, index) => <button
            key={item.id}
            type="button"
            className={cn("cr-hud__node", item.visited && "is-done", item.current && "is-current")}
            onClick={() => { onJump?.(item.id); setOpen(false); }}
            title={item.title}
          >
            <span>{index + 1}</span>
            {item.quizzed && <i aria-label="含测验" />}
          </button>)}
          {!map.length && <p className="cr-hud__empty">这一章还没有页面。</p>}
        </div>
      </section>

      <section className="cr-hud__section">
        <h3><Trophy size={14} /> 成就 <small>连击最高 ×{bestCombo}</small></h3>
        <ul className="cr-hud__badges">
          {ACHIEVEMENTS.map((item) => {
            const Icon = ICONS[item.icon] || Star;
            const has = earned.has(item.id);
            return <li key={item.id} className={cn("cr-hud__badge-item", has && "is-earned")} title={item.detail}>
              <Icon size={14} />
              <span>{item.label}</span>
            </li>;
          })}
        </ul>
      </section>
    </div>}
  </div>;
}

/**
 * 桌面端左侧的“本章冒险路线”。它是导航，也是进度：已探索、当前关、
 * 后面的关卡都从真实 `rewards.map` 读取；没有内容的场景不会被画成可跳转。
 */
export function ClassroomQuestMap({ map = [], total = 0, level, achievements = [], chapterTitle = "", onJump }) {
  const done = map.filter((item) => item.visited).length;
  const progress = total ? Math.min(100, Math.round((done / total) * 100)) : 0;
  const earned = new Set(achievements);

  return <section className="cr-quest" aria-label="本章冒险路线">
    <header className="cr-quest__head">
      <div>
        <span className="cr-quest__kicker">CHAPTER 01</span>
        <strong>{chapterTitle || "课堂冒险"}</strong>
      </div>
      <span className="cr-quest__count">{done}/{total || map.length}</span>
    </header>

    <div className="cr-quest__bar" aria-label={`本章进度 ${progress}%`}>
      <i style={{ width: `${progress}%` }} />
    </div>

    <ol className="cr-quest__path">
      {map.map((item, index) => <li key={item.id} className={cn(
        "cr-quest__stop",
        item.visited && "is-done",
        item.current && "is-current",
      )}>
        <button type="button" onClick={() => onJump?.(item.id)} title={item.title}>
          <span className="cr-quest__index">{index + 1}</span>
          <span className="cr-quest__copy">
            <strong>{item.title}</strong>
            <small>{item.current ? "当前关卡" : item.visited ? "已探索" : "未解锁"}</small>
          </span>
          {item.visited
            ? <Check size={13} />
            : item.current
              ? <span className="cr-quest__beacon" />
              : <Lock size={12} />}
        </button>
      </li>)}
      {!map.length && <li className="cr-quest__empty">本章还没有关卡。</li>}
    </ol>

    <footer className="cr-quest__foot">
      <span className="cr-quest__badges" aria-label={`已解锁 ${earned.size}/${ACHIEVEMENTS.length} 个成就`}>
        {ACHIEVEMENTS.slice(0, 4).map((item) => {
          const Icon = ICONS[item.icon] || Star;
          return <i key={item.id} className={cn(earned.has(item.id) && "is-earned")} title={item.label}>
            <Icon size={11} />
          </i>;
        })}
      </span>
      <span>再 {level?.toNext ?? 0} XP 升级</span>
    </footer>
  </section>;
}
