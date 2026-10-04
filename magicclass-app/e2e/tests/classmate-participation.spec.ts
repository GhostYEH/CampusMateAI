import { test, expect } from '../fixtures/base';
import { createSettingsStorage } from '../fixtures/test-data/settings';
import { defaultTheme } from '../fixtures/test-data/scene-content';

test('playing each page generates distinct panes for selected classmates', async ({
  page,
  mockApi,
}, testInfo) => {
  const screenshot = (name: string) =>
    page.screenshot({ path: testInfo.outputPath(name), animations: 'disabled' });
  await mockApi.mockServerProviders();
  await page.route('**/api/server-providers', (route) =>
    route.fulfill({
      json: {
        success: true,
        providers: {},
        tts: {},
        asr: {},
        pdf: {},
        image: {},
        video: {},
        webSearch: {},
        generation: { parallelSceneConcurrency: 3 },
      },
    }),
  );
  const selectedAgentIds = ['default-1', 'default-3', 'default-4'];
  const settings = createSettingsStorage({
    selectedAgentIds,
    sidebarCollapsed: false,
    autoPlayLecture: false,
  });
  await page.addInitScript((value) => {
    localStorage.setItem('maic:account:settings-storage', value);
    localStorage.setItem('locale', 'en-US');
  }, settings);
  const requests: { scene: { id: string }; agents: { id: string; persona: string }[] }[] = [];
  await page.route('**/api/chat/classmates', async (route) => {
    const body = route.request().postDataJSON();
    requests.push(body);
    await route.fulfill({
      json: {
        success: true,
        messages: body.agents.map((agent: { id: string }) => ({
          agentId: agent.id,
          text: `${body.scene.id}: ${agent.id} reaction`,
        })),
      },
    });
  });
  await page.goto('/', { waitUntil: 'networkidle' });
  await page.waitForFunction(async () =>
    (await indexedDB.databases()).some((db) => db.name === 'MAIC-Database'),
  );
  const seed = () =>
    page.evaluate(
      ({ theme, agentIds }) =>
        new Promise<void>((resolve, reject) => {
          const opening = indexedDB.open('MAIC-Database');
          opening.onerror = () => reject(opening.error);
          opening.onsuccess = () => {
            const db = opening.result;
            const tx = db.transaction(['stages', 'scenes', 'stageOutlines'], 'readwrite');
            const now = Date.now();
            tx.objectStore('stages').put({
              id: 'classmate-test',
              name: 'Classmate lesson',
              agentIds,
              createdAt: now,
              updatedAt: now,
            });
            for (let i = 0; i < 2; i++) {
              tx.objectStore('scenes').put({
                id: `classmate-page-${i}`,
                stageId: 'classmate-test',
                title: `Page ${i + 1}`,
                type: 'slide',
                order: i,
                content: {
                  type: 'slide',
                  canvas: {
                    id: `canvas-${i}`,
                    viewportSize: 1000,
                    viewportRatio: 0.5625,
                    theme,
                    elements: [
                      {
                        id: `text-${i}`,
                        type: 'text',
                        content: `<p>Lesson page ${i + 1}</p>`,
                        left: 50,
                        top: 50,
                        width: 900,
                        height: 100,
                      },
                    ],
                  },
                },
                actions: [
                  {
                    id: `speech-${i}`,
                    type: 'speech',
                    title: 'Teacher',
                    text: 'This page explains the lesson with an example.',
                  },
                ],
                createdAt: now,
                updatedAt: now,
              });
            }
            tx.objectStore('scenes').put({
              id: 'classmate-quiz',
              stageId: 'classmate-test',
              title: 'Quiz',
              type: 'quiz',
              order: 2,
              content: {
                type: 'quiz',
                questions: [
                  {
                    id: 'q1',
                    type: 'single',
                    question: 'Choose a fraction',
                    options: [
                      { value: 'A', label: '1/2' },
                      { value: 'B', label: 'text' },
                    ],
                    answer: ['A'],
                    analysis: 'A fraction has a numerator and denominator.',
                  },
                ],
              },
              actions: [],
              createdAt: now,
              updatedAt: now,
            });
            tx.objectStore('stageOutlines').put({
              stageId: 'classmate-test',
              outlines: [],
              createdAt: now,
              updatedAt: now,
            });
            tx.oncomplete = () => {
              db.close();
              resolve();
            };
            tx.onerror = () => reject(tx.error);
          };
        }),
      { theme: defaultTheme, agentIds: selectedAgentIds },
    );
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      await seed();
      break;
    } catch (error) {
      if (
        !(error instanceof Error) ||
        !error.message.includes('Execution context was destroyed') ||
        attempt === 2
      )
        throw error;
      await page.waitForLoadState('networkidle');
    }
  }
  await page.goto('/classroom/classmate-test');
  const panes = page.locator('article[data-classmate-id]');
  await expect(panes).toHaveCount(2, { timeout: 30_000 });
  expect(requests).toHaveLength(0);
  await page.keyboard.press('Space');
  await expect(page.locator('article[data-classmate-id="default-3"]')).toContainText(
    'classmate-page-0: default-3 reaction',
  );
  await expect(page.locator('article[data-classmate-id="default-4"]')).toContainText(
    'classmate-page-0: default-4 reaction',
  );
  expect(requests[0].agents.map((agent) => agent.id)).toEqual(['default-3', 'default-4']);
  expect(requests[0].agents.every((agent) => agent.persona.length > 0)).toBe(true);
  await screenshot('classmates-light.png');
  await page.emulateMedia({ colorScheme: 'dark' });
  await expect(page.locator('html')).toHaveClass(/dark/);
  await screenshot('classmates-dark.png');
  await page.emulateMedia({ colorScheme: 'light' });
  await expect(page.locator('html')).not.toHaveClass(/dark/);
  await page.getByRole('button', { name: 'Fullscreen', exact: true }).click();
  const teacherOverlay = page.getByTestId('presentation-teacher-overlay');
  const classmates = page.getByTestId('presentation-classmates');
  await expect(classmates).toBeVisible();
  const teacherBox = await teacherOverlay.boundingBox();
  const classmatesBox = await classmates.boundingBox();
  expect(teacherBox).not.toBeNull();
  expect(classmatesBox).not.toBeNull();
  expect(teacherBox!.y + teacherBox!.height).toBeLessThanOrEqual(classmatesBox!.y);
  await screenshot('classmates-presentation.png');
  await page.mouse.move(500, 700);
  await page.getByRole('button', { name: /exit fullscreen/i }).click();
  await expect(page.getByTestId('presentation-classmates')).toHaveCount(0);
  if (!(await page.locator('[data-testid="scene-item"]').nth(1).isVisible())) {
    await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
  }
  await page.locator('[data-testid="scene-item"]').nth(1).click();
  for (const id of ['default-3', 'default-4']) {
    await expect(page.locator(`article[data-classmate-id="${id}"]`)).not.toContainText(
      'classmate-page-0:',
    );
  }
  await page.keyboard.press('Space');
  await expect(page.locator('article[data-classmate-id="default-3"]')).toContainText(
    'classmate-page-1: default-3 reaction',
  );
  await expect(page.locator('article[data-classmate-id="default-4"]')).toContainText(
    'classmate-page-1: default-4 reaction',
  );
  await page.locator('[data-testid="scene-item"]').nth(2).click();
  await expect(page.locator('article[data-classmate-id="default-3"]')).toContainText(
    'classmate-quiz: default-3 reaction',
  );
  expect(requests.at(-1)?.scene.id).toBe('classmate-quiz');

  await page.locator('[data-testid="scene-item"]').first().click();
  const teacherCard = page.getByTestId('roundtable-non-presentation-card');
  const classmateRail = page.getByRole('region', { name: 'Classmates', exact: true });
  for (const width of [1024, 640]) {
    if (width === 640) {
      await page.getByRole('button', { name: 'Toggle sidebar', exact: true }).click();
    }
    await page.setViewportSize({ width, height: 720 });
    // The panes must leave a readable teacher area when the classroom itself is narrow.
    await expect
      .poll(async () => {
        const teacherBox = await teacherCard.boundingBox();
        const railBox = await classmateRail.boundingBox();
        return teacherBox && railBox ? railBox.y - (teacherBox.y + teacherBox.height) : -1;
      })
      .toBeGreaterThanOrEqual(0);
    for (let i = 0; i < 2; i++) {
      await panes.nth(i).scrollIntoViewIfNeeded();
      const paneBox = await panes.nth(i).boundingBox();
      const railBox = await classmateRail.boundingBox();
      expect(paneBox).not.toBeNull();
      expect(railBox).not.toBeNull();
      expect(paneBox!.x).toBeGreaterThanOrEqual(railBox!.x);
      expect(paneBox!.x + paneBox!.width).toBeLessThanOrEqual(railBox!.x + railBox!.width);
    }
    await panes.first().scrollIntoViewIfNeeded();
    await screenshot(`classmates-${width}.png`);
  }
  await page.keyboard.press('T');
  const textarea = page.getByPlaceholder('Type your message...', { exact: true });
  await expect(textarea).toBeVisible();
  await expect(page.getByTestId('roundtable-non-presentation-input-stage')).toHaveCSS(
    'transform',
    'none',
  );
  await textarea.fill(Array.from({ length: 20 }, (_, i) => `Question line ${i + 1}`).join('\n'));
  await expect(classmateRail).toBeHidden();
  await expect
    .poll(async () => {
      const inputBox = await page
        .getByTestId('roundtable-non-presentation-input-panel')
        .boundingBox();
      const teacherBox = await teacherCard.boundingBox();
      if (!inputBox || !teacherBox) return false;
      return (
        inputBox.x >= teacherBox.x &&
        inputBox.y >= teacherBox.y &&
        inputBox.x + inputBox.width <= teacherBox.x + teacherBox.width &&
        inputBox.y + inputBox.height <= teacherBox.y + teacherBox.height
      );
    })
    .toBe(true);
  await screenshot('classmates-narrow-input.png');
  await page.keyboard.press('Escape');
  await expect(classmateRail).toBeVisible();
});
