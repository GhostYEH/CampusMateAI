// @vitest-environment jsdom

import { act, createElement } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { Participant } from '@/lib/types/roundtable';
import {
  ClassmatePanes,
  useClassmateLiveSpeech,
  type ClassmateParticipation,
} from '@/components/roundtable/classmate-panes';

vi.mock('@/lib/hooks/use-i18n', () => ({
  useI18n: () => ({
    t: (key: string) =>
      ({
        'roundtable.classmates.title': 'Classmates',
        'roundtable.classmates.idle': 'Following this lesson',
        'roundtable.classmates.loading': 'Preparing a reaction...',
        'common.retry': 'Retry',
        'roundtable.classmates.previous': 'Previous classmates',
        'roundtable.classmates.next': 'Next classmates',
        'roundtable.classmates.discussionPending': 'Discussion pending',
        'roundtable.classmates.ask': 'Ask',
        'roundtable.classmates.askSubmit': 'Send',
        'roundtable.classmates.askPlaceholder': 'Ask this classmate a question',
        'roundtable.classmates.askLoading': 'Answering...',
        'roundtable.classmates.askError': 'The classmate could not answer. Try again.',
        'roundtable.classmates.quiet': 'Listening this time',
        'roundtable.classmates.budget': 'Class participation budget reached',
        'settings.agentDescriptions.curious': 'Asks why and how',
      })[key] || key,
  }),
}));

vi.mock('@/lib/orchestration/registry/store', () => ({
  useAgentRegistry: (select: (state: unknown) => unknown) =>
    select({ agents: { practical: { persona: 'Connects ideas with everyday examples' } } }),
}));

const participant = (id: string, role: Participant['role']): Participant => ({
  id,
  role,
  name: id,
  avatar: '🙂',
  isOnline: true,
});
const participants = [
  participant('teacher', 'teacher'),
  participant('curious', 'student'),
  participant('practical', 'student'),
  participant('user', 'user'),
];
const ready: ClassmateParticipation = {
  status: 'ready',
  error: null,
  messages: { curious: 'Why does it work?', practical: 'We can try this in daily life.' },
  retry: vi.fn(),
};

function Classroom({
  sceneKey = 'page-1',
  selected = participants,
  participation = ready,
  speakingAgentId,
  currentSpeech,
  discussionAgentId,
}: {
  sceneKey?: string;
  selected?: Participant[];
  participation?: ClassmateParticipation;
  speakingAgentId?: string | null;
  currentSpeech?: string | null;
  discussionAgentId?: string;
}) {
  const liveSpeech = useClassmateLiveSpeech({
    sceneKey,
    participants: selected,
    speakingAgentId,
    currentSpeech,
  });
  return createElement(ClassmatePanes, {
    key: sceneKey,
    participants: selected,
    participation,
    liveSpeech,
    speakingAgentId,
    discussionAgentId,
  });
}

describe('independent classmate panes', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });
  afterEach(() => {
    act(() => root.unmount());
    container.remove();
    vi.unstubAllGlobals();
  });
  const pane = (id: string) => container.querySelector(`[data-classmate-id="${id}"]`);

  it('shows only selected classmates with their own identity, style and reaction', () => {
    act(() => root.render(createElement(Classroom)));
    expect(pane('teacher')).toBeNull();
    expect(pane('user')).toBeNull();
    expect(pane('curious')?.textContent).toContain('Asks why and how');
    expect(pane('curious')?.textContent).toContain('Why does it work?');
    expect(pane('curious')?.textContent).not.toContain('daily life');
    expect(pane('practical')?.textContent).toContain('Connects ideas with everyday examples');
    act(() => root.render(createElement(Classroom, { selected: [participants[1]] })));
    expect(pane('practical')).toBeNull();
  });

  it('retains live speech by speaker and keeps automatic reactions from overriding it', () => {
    act(() =>
      root.render(
        createElement(Classroom, { speakingAgentId: 'curious', currentSpeech: 'Live why?' }),
      ),
    );
    act(() =>
      root.render(
        createElement(Classroom, { speakingAgentId: 'practical', currentSpeech: 'Live example' }),
      ),
    );
    act(() => root.render(createElement(Classroom, { participation: { ...ready, messages: {} } })));
    expect(pane('curious')?.textContent).toContain('Live why?');
    expect(pane('curious')?.textContent).not.toContain('Live example');
    expect(pane('practical')?.textContent).toContain('Live example');
    act(() =>
      root.render(
        createElement(Classroom, { speakingAgentId: 'teacher', currentSpeech: 'Lecture' }),
      ),
    );
    expect(container.textContent).not.toContain('Lecture');
    expect(pane('curious')?.textContent).toContain('Live why?');
  });

  it('marks the pending discussion classmate and lets buttons browse the overflowing rail', () => {
    act(() => root.render(createElement(Classroom, { discussionAgentId: 'practical' })));
    expect(pane('practical')?.querySelector('[data-discussion-pending]')).not.toBeNull();
    expect(pane('curious')?.querySelector('[data-discussion-pending]')).toBeNull();
    const rail = container.querySelector<HTMLDivElement>('[tabindex="0"]')!;
    const scrollBy = vi.fn();
    rail.scrollBy = scrollBy;
    act(() =>
      container.querySelector<HTMLButtonElement>('[aria-label="Next classmates"]')!.click(),
    );
    expect(scrollBy).toHaveBeenLastCalledWith(expect.objectContaining({ left: 180 }));
    act(() =>
      container.querySelector<HTMLButtonElement>('[aria-label="Previous classmates"]')!.click(),
    );
    expect(scrollBy).toHaveBeenLastCalledWith(expect.objectContaining({ left: -180 }));
  });

  it('clears every previous live turn when the scene key changes', () => {
    act(() =>
      root.render(
        createElement(Classroom, { speakingAgentId: 'curious', currentSpeech: 'Old page' }),
      ),
    );
    act(() => root.render(createElement(Classroom, { sceneKey: 'page-2' })));
    expect(container.textContent).not.toContain('Old page');
    expect(pane('curious')?.textContent).toContain('Why does it work?');
  });

  it('supports imported IDs matching object properties without phantom speech', () => {
    const ids = ['__proto__', 'constructor', 'toString'];
    const selected = ids.map((id) => participant(id, 'student'));
    const participation: ClassmateParticipation = {
      messages: {},
      status: 'idle',
      error: null,
      retry: vi.fn(),
    };
    act(() => root.render(createElement(Classroom, { selected, participation })));
    for (const id of ids) {
      expect(pane(id)?.textContent).toContain('Following this lesson');
    }
    act(() =>
      root.render(
        createElement(Classroom, {
          selected,
          participation: {
            ...participation,
            status: 'ready',
            messages: Object.fromEntries(ids.map((id) => [id, `${id} reaction`])),
          },
        }),
      ),
    );
    for (const id of ids) {
      expect(pane(id)?.textContent).toContain(`${id} reaction`);
    }
  });

  it('says a quiet classmate is listening instead of inventing a reaction', () => {
    act(() => root.render(createElement(Classroom, { participation: { ...ready, messages: {} } })));
    expect(pane('curious')?.textContent).toContain('Listening this time');
    expect(pane('curious')?.textContent).not.toContain('Following this lesson');
  });

  it('lets the student ask a named classmate and shows only their answer', async () => {
    const ask = vi.fn(async () => 'Gravity pulls it down.');
    const participation: ClassmateParticipation = { ...ready, messages: {}, ask };
    act(() => root.render(createElement(Classroom, { participation })));
    const open = container.querySelector<HTMLButtonElement>('[data-classmate-ask="curious"]')!;
    act(() => open.click());
    const input = container.querySelector<HTMLInputElement>(
      '[data-classmate-ask-input="curious"]',
    )!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
    act(() => {
      setValue.call(input, 'Why does it fall?');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    const submit = container.querySelector<HTMLButtonElement>(
      '[data-classmate-ask-submit="curious"]',
    )!;
    await act(async () => {
      submit.click();
    });
    expect(ask).toHaveBeenCalledWith('curious', 'Why does it fall?');
    expect(pane('curious')?.textContent).toContain('Gravity pulls it down.');
    expect(pane('practical')?.textContent).toContain('Listening this time');
  });

  it('hides asking and shows a notice when the course budget is spent', () => {
    act(() =>
      root.render(createElement(Classroom, { participation: { ...ready, budgetLimited: true } })),
    );
    expect(container.querySelector('[data-classmate-ask]')).toBeNull();
    expect(container.textContent).toContain('Class participation budget reached');
  });

  it('shows loading, the real error and a working retry without invented speech', () => {
    const retry = vi.fn();
    act(() =>
      root.render(
        createElement(Classroom, {
          participation: { messages: {}, status: 'loading', error: null, retry },
        }),
      ),
    );
    expect(container.querySelectorAll('[role="status"]')).toHaveLength(2);
    expect(container.textContent).not.toContain('Why does it work?');
    act(() =>
      root.render(
        createElement(Classroom, {
          participation: { messages: {}, status: 'error', error: 'Provider timed out', retry },
        }),
      ),
    );
    expect(pane('curious')?.textContent).toContain('Provider timed out');
    act(() => pane('curious')?.querySelector('button')?.click());
    expect(retry).toHaveBeenCalledOnce();
    act(() =>
      root.render(
        createElement(Classroom, {
          participation: { messages: {}, status: 'idle', error: null, retry },
        }),
      ),
    );
    expect(pane('curious')?.textContent).toContain('Following this lesson');
  });
});
