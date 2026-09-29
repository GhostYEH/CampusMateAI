import { describe, expect, it } from 'vitest';
import { buildPrompt, PROMPT_IDS } from '@magicclass/generation';

describe('slide action narration prompt', () => {
  it('builds a paced, evidence-grounded walkthrough from the supplied slide context', () => {
    const prompt = buildPrompt(PROMPT_IDS.SLIDE_ACTIONS, {
      title: 'Energy Conservation',
      keyPoints: '1. Potential energy converts into kinetic energy.',
      description: 'A formula connects height, mass, and gravitational acceleration.',
      elements: '- id: "formula_1", type: "latex", Formula: "E_p = mgh"',
      courseContext: 'Course Outline: Energy and motion',
      agents: '',
      userProfile: '',
      languageDirective: 'Teach in Chinese.',
    });

    expect(prompt).not.toBeNull();
    expect(prompt!.system).toContain('2-3 spoken beats for a sparse page');
    expect(prompt!.system).toContain('3-5 for a dense page');
    expect(prompt!.system).toContain('35-80 Chinese characters');
    expect(prompt!.system).toContain(
      'Anchor every body segment in a specific phrase, formula, label, or relationship',
    );
    expect(prompt!.system).toContain('do not invent its labels, values, trends, or visual contents');
    expect(prompt!.system).toContain('spotlight or laser immediately before the speech');
    expect(prompt!.user).toContain('formula_1');
    expect(prompt!.user).toContain('E_p = mgh');
    expect(prompt!.user).toContain('Teach in Chinese.');
    expect(`${prompt!.system}\n${prompt!.user}`).not.toMatch(/\{\{\w[\w-]*\}\}/);
  });
});
