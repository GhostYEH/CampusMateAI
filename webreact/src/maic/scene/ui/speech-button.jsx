import { Mic } from 'lucide-react';

import { cn } from '../../utils/cn.js';

/**
 * 参考项目 `components/audio/speech-button.tsx` 的**近似替换**。
 *
 * 上游把麦克风按钮接到 `useAudioRecorder`（浏览器 ASR + 服务端转写）和
 * `useASRAvailable`（设置里的开关 + provider 配置）上，并用 Radix Tooltip 包一层。
 * 目标项目既没有 ASR 运行时，也没有设置 store 和 `ui/tooltip`，因此这里保留：
 *   - **完全相同的 props 签名**（`onTranscription` / `className` / `disabled` /
 *     `size` / `continuous`），调用点无需改写；
 *   - **相同的 DOM 结构与类名**（按钮容器、尺寸档位、图标尺寸、禁用态样式），
 *     保证 quiz 简答题输入框左下角的按钮位置与观感一致；
 *   - 相同的 `shouldCancelRecordingOnDisable` 纯函数导出。
 * 差别：没有录音能力，因此按钮恒定 `disabled`，用原生 `title` 代替 Radix Tooltip，
 * 文案取自 zh-CN 的 `voice.startListening`（"语音输入"）。
 *
 * 视觉上按钮看起来与上游的"未录音"状态一致，只是不可点击。
 */
export function shouldCancelRecordingOnDisable(args) {
  return !!args.continuous && !!args.disabled && args.isRecording;
}

export function SpeechButton({ className, disabled, size = 'sm' }) {
  const isMd = size === 'md';
  const sizeClasses = isMd ? 'h-8 w-8' : 'h-6 w-6';
  const iconSize = isMd ? 'w-4 h-4' : 'w-3.5 h-3.5';

  return (
    <button
      type="button"
      disabled
      title="语音输入"
      aria-label="语音输入"
      data-maic-speech-button="unavailable"
      className={cn(
        'relative flex items-center justify-center rounded-lg transition-all duration-200 shrink-0',
        sizeClasses,
        'text-muted-foreground/60',
        'opacity-40 pointer-events-none',
        className,
      )}
      data-disabled={disabled === undefined ? undefined : String(!!disabled)}
    >
      <Mic className={cn(iconSize, 'relative z-10')} />
    </button>
  );
}
