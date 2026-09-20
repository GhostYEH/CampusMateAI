import * as React from "react";
import { BookOpen, Loader2, MessageSquare, Send, Users } from "lucide-react";

import { cn } from "../utils/cn.js";
import {
  discussionRejection,
  discussionSpeakers,
  speakerColor,
  speakerInitial,
} from "../../features/openmaic/roundtableModel.js";

/**
 * 圆桌讨论面板——逐字移植参考项目 `components/roundtable/index.tsx` 的**外框与三栏
 * 结构**（第 1138-1170 行、第 1862-1870 行）：
 *
 *   <div className="h-[192px] w-full flex flex-col relative z-10 transition-all duration-300
 *                   border-t border-gray-100 dark:border-gray-800 bg-white/60 dark:bg-gray-800/60 backdrop-blur-md">
 *     <div>{toolbar}</div>                      // Toolbar strip — merged from CanvasArea
 *     <div className="flex-1 flex items-stretch min-h-0">
 *       <div className="w-[90px]  ... border-r ...">   // 左：主讲人
 *       <div className="flex-1   ...">                 // 中：发言气泡
 *       <div className="w-[140px] ... border-l ...">   // 右：参与者
 *     </div>
 *   </div>
 *
 * 参考项目里那句注释是关键：**播放态的工具栏并没有被丢弃，而是并进了圆桌的顶部条**
 * （`canvas-area.tsx` 的 `hideToolbar={mode === 'playback'}` 正是这个意思）。所以这里
 * 由 `toolbar` 属性接住工具栏，而不是自己再画一条。
 *
 * ## 与参考实现的差异（都在"没有对应运行时"这一类）
 *
 * - **没有逐智能体语音**：参考的圆桌会给每个发言人合成 TTS 并按音频波形驱动头像光晕。
 *   本服务只回文本，所以头像不做波形，也不放一个按了没声的喇叭按钮。
 * - **没有实时流式**：参考边生成边逐字上屏；讨论是任务式的，因此运行中显示的是
 *   三点脉冲而不是假装在逐字输出。
 * - **没有真人头像图**：参考从智能体配置取 `avatar`，本服务不提供，因此用名字首字
 *   加派生色做头像——不编一张不存在的图，也不会出现破图。
 * - **没有麦克风/ASR**：不放麦克风按钮。
 *
 * 保留的行为：外框高度与毛玻璃、三栏宽度与分隔线、主讲人激活环、气泡升起动画、
 * 自适应滚动、参与者栏按出场顺序。
 */
export function MaicRoundtable({
  toolbar,
  messages = [],
  busy = false,
  error = "",
  prompt = "",
  onPromptChange,
  onStart,
  sceneTitle = "",
}) {
  const speakers = React.useMemo(() => discussionSpeakers(messages), [messages]);
  const errorText = typeof error === "string" ? error : "";
  const rejection = discussionRejection({ prompt, busy });
  const listRef = React.useRef(null);

  // 新发言到达时滚到底部：讨论是顺序阅读的，停在顶部等于把最新一轮藏起来。
  React.useEffect(() => {
    const node = listRef.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [messages.length, busy]);

  const teacher = speakers[0] ?? null;
  const participants = speakers.length > 1 ? speakers.slice(1) : [];

  return (
    <div className="maic-root h-[192px] w-full flex flex-col relative z-10 transition-all duration-300 border-t border-gray-100 dark:border-gray-800 bg-white/60 dark:bg-gray-800/60 backdrop-blur-md">
      {/* Toolbar strip — 参考项目把画布工具栏并进了这里 */}
      <div className="transition-opacity duration-300">{toolbar}</div>

      <div className="flex-1 flex items-stretch min-h-0">
        {/* 左：主讲人 */}
        <div className="w-[90px] shrink-0 flex flex-col border-r border-gray-100/50 dark:border-gray-700/50 bg-white/40 dark:bg-gray-900/40 relative overflow-hidden">
          <div className="absolute top-0 inset-x-0 h-16 bg-gradient-to-b from-purple-50/50 dark:from-purple-900/10 to-transparent pointer-events-none" />
          <div className="absolute top-3 inset-x-0 flex flex-col items-center justify-center gap-1 opacity-10 pointer-events-none">
            <BookOpen size={20} className="text-purple-900 dark:text-purple-100" />
            <div className="w-8 h-0.5 bg-purple-900 dark:bg-purple-100 rounded-full" />
          </div>
          <div className="flex-1 flex flex-col items-center justify-center gap-1.5 px-2 pt-6 min-h-0 relative">
            <div
              className={cn(
                "relative w-12 h-12 rounded-full transition-all duration-500 flex items-center justify-center",
                busy ? "scale-105" : "opacity-90 scale-95",
              )}
            >
              <div
                className={cn(
                  "absolute inset-0 rounded-full border-2 transition-all duration-500",
                  busy
                    ? "border-purple-500 dark:border-purple-400 shadow-[0_0_12px_rgba(168,85,247,0.4)]"
                    : "border-gray-200 dark:border-gray-700",
                )}
              />
              <div className="w-10 h-10 rounded-full bg-white dark:bg-gray-800 z-10 shadow-sm border border-gray-50 dark:border-gray-700 flex items-center justify-center text-sm font-black text-purple-700 dark:text-purple-300">
                {speakerInitial(teacher?.name || "主讲")}
              </div>
            </div>
            <span className="text-[10px] font-bold text-gray-500 dark:text-gray-400 truncate max-w-full">
              {teacher?.name || "课堂主持"}
            </span>
          </div>
        </div>

        {/* 中：发言气泡 */}
        <div className="flex-1 min-w-0 flex flex-col relative">
          {errorText ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-1.5 px-4 text-center" role="alert">
              <MessageSquare className="w-4 h-4 text-red-400" />
              <p className="text-[12px] text-red-600 dark:text-red-400">{errorText}</p>
              <button
                type="button"
                onClick={onStart}
                disabled={Boolean(rejection)}
                className="mt-0.5 px-3 h-6 rounded-md text-[11px] font-semibold bg-white/70 dark:bg-gray-800/70 border border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700/60 active:scale-95 transition-all disabled:opacity-40 disabled:pointer-events-none"
              >
                重试
              </button>
            </div>
          ) : messages.length ? (
            <div ref={listRef} className="flex-1 min-h-0 overflow-y-auto px-3 py-2 space-y-2">
              {messages.map((message, index) => {
                const color = speakerColor(message.agent);
                return (
                  <div
                    key={`${message.agent}-${index}`}
                    className="relative group/bubble rounded-xl border bg-white/70 dark:bg-gray-800/60 px-3 py-2 shadow-[0_1px_2px_rgba(15,23,42,0.04)] animate-[fadeInUp_.24s_ease-out]"
                    style={{ borderColor: `${color.ring}33` }}
                  >
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span
                        className="w-3.5 h-3.5 rounded-full flex items-center justify-center text-[8px] font-black shrink-0"
                        style={{ backgroundColor: color.bg, color: color.text }}
                      >
                        {speakerInitial(message.agent)}
                      </span>
                      <span className="text-[10px] font-bold" style={{ color: color.text }}>
                        {message.agent}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap break-words text-[12px] leading-relaxed text-gray-700 dark:text-gray-200">
                      {message.content}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : busy ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-2" role="status">
              <div className="flex gap-1 items-center">
                {[0, 1, 2].map((index) => (
                  <span
                    key={index}
                    className="w-1.5 h-1.5 rounded-full bg-purple-400 dark:bg-purple-500 animate-[thinkDotPulse_1s_ease-in-out_infinite]"
                    style={{ animationDelay: `${index * 0.2}s` }}
                  />
                ))}
              </div>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 font-medium">正在组织讨论…</p>
            </div>
          ) : (
            <form
              className="flex-1 flex flex-col items-center justify-center gap-1.5 px-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (!rejection) onStart?.();
              }}
            >
              <div className="flex items-center gap-1.5">
                <Users className="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
                <span className="text-[11px] font-semibold text-gray-500 dark:text-gray-400">
                  圆桌讨论
                </span>
              </div>
              <div className="w-full max-w-[520px] flex items-center gap-1.5">
                <input
                  value={prompt}
                  onChange={(event) => onPromptChange?.(event.target.value)}
                  maxLength={2000}
                  aria-label="圆桌讨论主题"
                  placeholder={sceneTitle ? `围绕「${sceneTitle}」讨论…` : "输入想讨论的主题"}
                  className="flex-1 h-7 rounded-md bg-white/80 dark:bg-gray-900/50 border border-gray-200 dark:border-gray-700 px-2.5 text-[12px] text-gray-700 dark:text-gray-200 outline-none focus:border-purple-300 dark:focus:border-purple-600 transition-colors"
                />
                <button
                  type="submit"
                  disabled={Boolean(rejection)}
                  className="h-7 px-3 rounded-md text-[11px] font-bold text-white bg-purple-600 hover:bg-purple-500 active:scale-95 transition-all disabled:opacity-40 disabled:pointer-events-none inline-flex items-center gap-1"
                >
                  <Send className="w-3 h-3" />
                  开始讨论
                </button>
              </div>
            </form>
          )}
        </div>

        {/* 右：参与者 */}
        <div className="w-[140px] shrink-0 flex flex-col border-l border-gray-100/50 dark:border-gray-700/50 bg-gray-50/30 dark:bg-gray-900/30 py-2 px-2 min-h-0">
          <span className="text-[9px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500 mb-1">
            参与者
          </span>
          <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-1.5">
            {participants.length ? (
              participants.map((speaker) => (
                <div key={speaker.name} className="flex items-center gap-1.5 min-w-0">
                  <span
                    className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-black shrink-0"
                    style={{ backgroundColor: speaker.color.bg, color: speaker.color.text }}
                  >
                    {speakerInitial(speaker.name)}
                  </span>
                  <span className="text-[10px] font-semibold text-gray-600 dark:text-gray-300 truncate">
                    {speaker.name}
                  </span>
                </div>
              ))
            ) : (
              <span className="text-[10px] text-gray-400 dark:text-gray-500 leading-snug">
                讨论开始后，参与的角色会出现在这里。
              </span>
            )}
          </div>
          {busy ? (
            <div className="flex items-center gap-1 pt-1 text-gray-400 dark:text-gray-500">
              <Loader2 className="w-3 h-3 animate-spin" />
              <span className="text-[9px] font-medium">进行中</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
