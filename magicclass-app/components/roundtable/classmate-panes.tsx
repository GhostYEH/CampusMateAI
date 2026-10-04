'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AvatarDisplay } from '@/components/ui/avatar-display';
import { useI18n } from '@/lib/hooks/use-i18n';
import { useAgentRegistry } from '@/lib/orchestration/registry/store';
import type { Participant } from '@/lib/types/roundtable';
import { cn } from '@/lib/utils';

export interface ClassmateParticipation {
  messages: Record<string, string>;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
  retry: () => void;
}

/** Keep each speaker's last live turn for this page, independently of automatic reactions. */
export function useClassmateLiveSpeech({
  sceneKey,
  participants,
  speakingAgentId,
  currentSpeech,
}: {
  sceneKey: string;
  participants: Participant[];
  speakingAgentId?: string | null;
  currentSpeech?: string | null;
}) {
  const [cache, setCache] = useState<{ sceneKey: string; messages: Record<string, string> }>({
    sceneKey,
    messages: {},
  });
  let messages = cache.sceneKey === sceneKey ? cache.messages : {};
  const isClassmate = participants.some(
    (participant) =>
      participant.id === speakingAgentId &&
      participant.role !== 'teacher' &&
      participant.role !== 'user',
  );
  if (isClassmate && speakingAgentId && currentSpeech?.trim()) {
    if (messages[speakingAgentId] !== currentSpeech) {
      messages = { ...messages, [speakingAgentId]: currentSpeech };
    }
  }
  // Adjust on prop changes during render so a new page never paints the old page's turns.
  if (cache.sceneKey !== sceneKey || cache.messages !== messages) {
    setCache({ sceneKey, messages });
  }
  return messages;
}

export function ClassmatePanes({
  participants,
  participation,
  liveSpeech = {},
  speakingAgentId,
  thinkingAgentId,
  onAvatarRef,
  className,
}: {
  readonly participants: Participant[];
  readonly participation?: ClassmateParticipation;
  readonly liveSpeech?: Record<string, string>;
  readonly speakingAgentId?: string | null;
  readonly thinkingAgentId?: string;
  readonly onAvatarRef?: (id: string, element: HTMLDivElement | null) => void;
  readonly className?: string;
}) {
  const { t } = useI18n();
  const agents = useAgentRegistry((state) => state.agents);
  const classmates = participants.filter((p) => p.role !== 'teacher' && p.role !== 'user');
  if (!classmates.length) return null;

  return (
    <section
      aria-label={t('roundtable.classmates.title')}
      className={cn('flex min-w-0 gap-2 overflow-x-auto overscroll-x-contain p-2', className)}
    >
      {classmates.map((classmate) => {
        const localizedDescription = t(`settings.agentDescriptions.${classmate.id}`);
        const description =
          localizedDescription !== `settings.agentDescriptions.${classmate.id}`
            ? localizedDescription
            : agents[classmate.id]?.persona || t('roundtable.classmates.style');
        const liveText = Object.hasOwn(liveSpeech, classmate.id)
          ? liveSpeech[classmate.id]
          : undefined;
        const generatedText =
          participation && Object.hasOwn(participation.messages, classmate.id)
            ? participation.messages[classmate.id]
            : undefined;
        const text = liveText || generatedText;
        const speaking = speakingAgentId === classmate.id;
        const loading = thinkingAgentId === classmate.id || participation?.status === 'loading';
        return (
          <article
            key={classmate.id}
            data-classmate-id={classmate.id}
            aria-label={classmate.name}
            className={cn(
              'flex h-full w-52 shrink-0 flex-col rounded-lg border bg-white/80 p-2 dark:bg-gray-900/80',
              speaking
                ? 'border-purple-400 dark:border-purple-500'
                : 'border-gray-200 dark:border-gray-700',
            )}
          >
            <header className="flex shrink-0 items-center gap-2">
              <div
                ref={(element) => onAvatarRef?.(classmate.id, element)}
                data-agent-id={classmate.id}
                className="h-7 w-7 shrink-0 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800"
              >
                <AvatarDisplay src={classmate.avatar} alt={classmate.name} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-medium">{classmate.name}</p>
                <p className="truncate text-[10px] text-muted-foreground" title={description}>
                  {description}
                </p>
              </div>
              {speaking && (
                <span className="text-[10px] text-purple-600 dark:text-purple-300">
                  {t('roundtable.classmates.speaking')}
                </span>
              )}
            </header>
            <div className="mt-1.5 min-h-0 flex-1 overflow-y-auto text-xs leading-relaxed">
              {text ? (
                <p className="whitespace-pre-wrap break-words">{text}</p>
              ) : loading ? (
                <p role="status" className="flex items-center gap-1 text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {t('roundtable.classmates.loading')}
                </p>
              ) : participation?.status === 'error' ? (
                <div>
                  <p className="break-words text-red-600 dark:text-red-400">
                    {participation.error || t('roundtable.classmates.error')}
                  </p>
                  <button
                    type="button"
                    onClick={participation.retry}
                    className="mt-1 text-purple-600 underline dark:text-purple-300"
                  >
                    {t('common.retry')}
                  </button>
                </div>
              ) : (
                <p className="text-muted-foreground">{t('roundtable.classmates.idle')}</p>
              )}
            </div>
          </article>
        );
      })}
    </section>
  );
}
