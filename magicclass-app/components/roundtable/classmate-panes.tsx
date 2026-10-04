'use client';

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { AvatarDisplay } from '@/components/ui/avatar-display';
import { Button } from '@/components/ui/button';
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
  compact = false,
  className,
}: {
  readonly participants: Participant[];
  readonly participation?: ClassmateParticipation;
  readonly liveSpeech?: Record<string, string>;
  readonly speakingAgentId?: string | null;
  readonly thinkingAgentId?: string;
  readonly onAvatarRef?: (id: string, element: HTMLDivElement | null) => void;
  readonly compact?: boolean;
  readonly className?: string;
}) {
  const { t } = useI18n();
  const agents = useAgentRegistry((state) => state.agents);
  const classmates = participants.filter((p) => p.role !== 'teacher' && p.role !== 'user');
  if (!classmates.length) return null;

  return (
    <section
      aria-label={t('roundtable.classmates.title')}
      tabIndex={0}
      className={cn(
        'flex min-w-0 gap-3 overflow-x-auto overscroll-x-contain scroll-p-3 snap-x snap-proximity rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-primary/25',
        compact ? 'p-2' : 'p-3 @max-[800px]/roundtable:gap-2 @max-[800px]/roundtable:p-2',
        className,
      )}
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
              'flex h-full w-60 max-w-full shrink-0 snap-start flex-col rounded-2xl border bg-gradient-to-b from-card/95 to-card/65 text-card-foreground shadow-sm backdrop-blur-sm transition-colors duration-200 motion-reduce:transition-none dark:from-gray-800/95 dark:to-gray-800/65',
              classmates.length === 2 && 'basis-0 grow min-w-[min(180px,100%)]',
              compact ? 'p-2.5' : 'p-3 @max-[800px]/roundtable:p-2',
              speaking ? 'border-primary/40 ring-1 ring-primary/10' : 'border-border/60',
            )}
          >
            <header className="flex shrink-0 items-center gap-2">
              <div
                ref={(element) => onAvatarRef?.(classmate.id, element)}
                data-agent-id={classmate.id}
                className={cn(
                  'h-8 w-8 shrink-0 overflow-hidden rounded-full border border-border/60 bg-muted',
                  !compact && '@max-[800px]/roundtable:h-6 @max-[800px]/roundtable:w-6',
                  speaking && 'border-primary/30',
                )}
              >
                <AvatarDisplay src={classmate.avatar} alt={classmate.name} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] font-semibold leading-5" title={classmate.name}>
                  {classmate.name}
                </p>
                <p
                  className={cn(
                    'truncate text-[11px] leading-4 text-muted-foreground',
                    !compact && '@max-[800px]/roundtable:hidden',
                  )}
                  title={description}
                >
                  {description}
                </p>
              </div>
              {speaking && (
                <span className="shrink-0 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                  {t('roundtable.classmates.speaking')}
                </span>
              )}
            </header>
            <div className="mt-2 min-h-0 flex-1 overflow-y-auto text-[13px] leading-5 @max-[800px]/roundtable:mt-1 @max-[800px]/roundtable:text-xs @max-[800px]/roundtable:leading-[18px]">
              {text ? (
                <p className="whitespace-pre-wrap break-words">{text}</p>
              ) : loading ? (
                <p role="status" className="flex items-center gap-1 text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {t('roundtable.classmates.loading')}
                </p>
              ) : participation?.status === 'error' ? (
                <div>
                  <p className="break-words text-destructive">
                    {participation.error || t('roundtable.classmates.error')}
                  </p>
                  <Button
                    type="button"
                    onClick={participation.retry}
                    variant="link"
                    size="xs"
                    className="mt-1 px-0"
                  >
                    {t('common.retry')}
                  </Button>
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
