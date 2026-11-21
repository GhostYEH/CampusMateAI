'use client';

import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, Loader2, MessageCircle, Send } from 'lucide-react';
import { AvatarDisplay } from '@/components/ui/avatar-display';
import { Button } from '@/components/ui/button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { useI18n } from '@/lib/hooks/use-i18n';
import { useAgentRegistry } from '@/lib/orchestration/registry/store';
import type { Participant } from '@/lib/types/roundtable';
import { cn } from '@/lib/utils';

export interface ClassmateParticipation {
  messages: Record<string, string>;
  status: 'idle' | 'loading' | 'ready' | 'error';
  error: string | null;
  retry: () => void;
  /** Ask one named classmate directly; the answer is page-scoped. */
  ask?: (agentId: string, question: string) => Promise<string>;
  /** The course-level class participation budget is spent: no new reactions or answers. */
  budgetLimited?: boolean;
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
  discussionAgentId,
  portalContainer,
  onAvatarRef,
  compact = false,
  className,
}: {
  readonly participants: Participant[];
  readonly participation?: ClassmateParticipation;
  readonly liveSpeech?: Record<string, string>;
  readonly speakingAgentId?: string | null;
  readonly thinkingAgentId?: string;
  readonly discussionAgentId?: string;
  readonly portalContainer?: HTMLElement | null;
  readonly onAvatarRef?: (id: string, element: HTMLDivElement | null) => void;
  readonly compact?: boolean;
  readonly className?: string;
}) {
  const { t } = useI18n();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [askFor, setAskFor] = useState<string | null>(null);
  const [draft, setDraft] = useState('');
  const [asked, setAsked] = useState<Record<string, string>>({});
  const [asking, setAsking] = useState<
    Record<string, { status: 'loading' | 'error'; error?: string }>
  >({});

  const submitQuestion = async (agentId: string) => {
    const question = draft.trim();
    if (!participation?.ask || !question) return;
    setAsking((state) => ({ ...state, [agentId]: { status: 'loading' } }));
    try {
      const answer = await participation.ask(agentId, question);
      setAsked((state) => ({ ...state, [agentId]: answer }));
      setAsking((state) => {
        const next = { ...state };
        delete next[agentId];
        return next;
      });
      setAskFor(null);
      setDraft('');
    } catch (error) {
      setAsking((state) => ({
        ...state,
        [agentId]: {
          status: 'error',
          error: error instanceof Error ? error.message : undefined,
        },
      }));
    }
  };
  const agents = useAgentRegistry((state) => state.agents);
  const classmates = participants.filter((p) => p.role !== 'teacher' && p.role !== 'user');
  useEffect(() => {
    const rail = scrollRef.current;
    if (!rail) return;
    const onWheel = (event: WheelEvent) => {
      // Leave speech panes' vertical scrolling and page scroll at rail edges intact.
      if (event.target instanceof Element && event.target.closest('[data-classmate-speech]'))
        return;
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) return;
      const before = rail.scrollLeft;
      rail.scrollLeft += event.deltaY;
      if (rail.scrollLeft !== before) event.preventDefault();
    };
    rail.addEventListener('wheel', onWheel, { passive: false });
    return () => rail.removeEventListener('wheel', onWheel);
  }, [classmates.length]);
  if (!classmates.length) return null;

  return (
    <section
      aria-label={t('roundtable.classmates.title')}
      className={cn('group/classmates relative min-w-0', className)}
    >
      <div
        ref={scrollRef}
        tabIndex={0}
        className={cn(
          'flex h-full min-w-0 gap-3 overflow-x-auto overscroll-x-contain scroll-p-3 snap-x snap-proximity rounded-2xl outline-none focus-visible:ring-2 focus-visible:ring-primary/25',
          compact ? 'p-2' : 'p-3 @max-[800px]/roundtable:gap-2 @max-[800px]/roundtable:p-2',
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
          const answerText = Object.hasOwn(asked, classmate.id) ? asked[classmate.id] : undefined;
          const askState = Object.hasOwn(asking, classmate.id)
            ? asking[classmate.id].status
            : undefined;
          const text = answerText || liveText || generatedText;
          const speaking = speakingAgentId === classmate.id;
          const discussion = discussionAgentId === classmate.id;
          const config = agents[classmate.id];
          const role = config?.role || classmate.role;
          const roleKey = `settings.agentRoles.${role}`;
          const roleLabel = t(roleKey) === roleKey ? role : t(roleKey);
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
                <HoverCard openDelay={300} closeDelay={100}>
                  <HoverCardTrigger asChild>
                    <div
                      tabIndex={0}
                      ref={(element) => onAvatarRef?.(classmate.id, element)}
                      data-agent-id={classmate.id}
                      className={cn(
                        'relative h-8 w-8 shrink-0 rounded-full border border-border/60 bg-muted outline-none focus-visible:ring-2 focus-visible:ring-primary/50',
                        !compact && '@max-[800px]/roundtable:h-6 @max-[800px]/roundtable:w-6',
                        speaking && 'border-primary/30',
                      )}
                    >
                      {discussion && (
                        <span
                          data-discussion-pending={classmate.id}
                          aria-label={t('roundtable.classmates.discussionPending')}
                          className="absolute -inset-1 rounded-full border-2 animate-pulse motion-reduce:animate-none"
                          style={{ borderColor: config?.color || 'var(--primary)' }}
                        />
                      )}
                      <div className="h-full w-full overflow-hidden rounded-full">
                        <AvatarDisplay src={classmate.avatar} alt={classmate.name} />
                      </div>
                    </div>
                  </HoverCardTrigger>
                  <HoverCardContent
                    container={portalContainer}
                    className="max-h-[300px] overflow-y-auto"
                  >
                    <p className="font-medium">{classmate.name}</p>
                    <span
                      className="mt-1 inline-block rounded-full px-2 py-0.5 text-xs text-white"
                      style={{ backgroundColor: config?.color || '#d97706' }}
                    >
                      {roleLabel}
                    </span>
                    <p className="mt-2 whitespace-pre-line text-xs leading-relaxed text-muted-foreground">
                      {description}
                    </p>
                  </HoverCardContent>
                </HoverCard>
                <div className="min-w-0 flex-1">
                  <p
                    className="truncate text-[13px] font-semibold leading-5"
                    title={classmate.name}
                  >
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
                {participation?.ask && !participation.budgetLimited && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    data-classmate-ask={classmate.id}
                    aria-label={`${t('roundtable.classmates.ask')}: ${classmate.name}`}
                    aria-expanded={askFor === classmate.id}
                    disabled={askState === 'loading'}
                    onClick={() => {
                      setAskFor(askFor === classmate.id ? null : classmate.id);
                      setDraft('');
                      setAsking((state) => {
                        if (!Object.hasOwn(state, classmate.id)) return state;
                        const next = { ...state };
                        delete next[classmate.id];
                        return next;
                      });
                    }}
                    className="h-6 w-6 shrink-0 text-muted-foreground hover:text-foreground"
                  >
                    <MessageCircle className="h-3.5 w-3.5" />
                  </Button>
                )}
              </header>
              <div
                data-classmate-speech
                className="mt-2 min-h-0 flex-1 overflow-y-auto text-[13px] leading-5 @max-[800px]/roundtable:mt-1 @max-[800px]/roundtable:text-xs @max-[800px]/roundtable:leading-[18px]"
              >
                {text ? (
                  <p className="whitespace-pre-wrap break-words">{text}</p>
                ) : askState === 'loading' ? (
                  <p role="status" className="flex items-center gap-1 text-muted-foreground">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {t('roundtable.classmates.askLoading')}
                  </p>
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
                ) : participation?.status === 'ready' ? (
                  <p className="text-muted-foreground">{t('roundtable.classmates.quiet')}</p>
                ) : (
                  <p className="text-muted-foreground">{t('roundtable.classmates.idle')}</p>
                )}
              </div>
              {askFor === classmate.id && participation?.ask && (
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    void submitQuestion(classmate.id);
                  }}
                  className="mt-2 flex shrink-0 items-center gap-1"
                >
                  <input
                    autoFocus
                    value={draft}
                    maxLength={600}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={t('roundtable.classmates.askPlaceholder')}
                    aria-label={`${t('roundtable.classmates.askPlaceholder')} ${classmate.name}`}
                    data-classmate-ask-input={classmate.id}
                    className="h-6 min-w-0 flex-1 rounded-md border border-border/60 bg-background px-1.5 text-[12px] outline-none focus-visible:border-primary/50"
                  />
                  <Button
                    type="submit"
                    size="icon"
                    data-classmate-ask-submit={classmate.id}
                    aria-label={t('roundtable.classmates.askSubmit')}
                    disabled={!draft.trim() || askState === 'loading'}
                    className="h-6 w-6 shrink-0"
                  >
                    <Send className="h-3 w-3" />
                  </Button>
                </form>
              )}
              {askState === 'error' && (
                <p role="alert" className="mt-1 shrink-0 text-[11px] leading-4 text-destructive">
                  {asking[classmate.id]?.error || t('roundtable.classmates.askError')}
                </p>
              )}
            </article>
          );
        })}
      </div>
      {classmates.length > 1 &&
        (['previous', 'next'] as const).map((direction) => (
          <Button
            key={direction}
            type="button"
            variant="ghost"
            size="icon"
            aria-label={t(`roundtable.classmates.${direction}`)}
            onClick={() =>
              scrollRef.current?.scrollBy({
                left:
                  (direction === 'previous' ? -1 : 1) *
                  Math.max(180, scrollRef.current.clientWidth * 0.8),
                behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
                  ? 'instant'
                  : 'smooth',
              })
            }
            className={cn(
              'absolute bottom-1 h-6 w-6 bg-card/90 opacity-70 transition-opacity hover:opacity-100 focus-visible:opacity-100',
              direction === 'previous' ? 'left-1' : 'right-1',
            )}
          >
            {direction === 'previous' ? (
              <ChevronLeft className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </Button>
        ))}

      {participation?.budgetLimited && (
        <p role="status" className="px-1 pt-1 text-[11px] leading-4 text-muted-foreground">
          {t('roundtable.classmates.budget')}
        </p>
      )}
    </section>
  );
}
