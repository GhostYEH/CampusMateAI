import { expect, it } from 'vitest';
import { existsSync } from 'node:fs';
import { chromium } from '@playwright/test';
import { patchHtmlForIframe } from '@/lib/utils/iframe';
import { postProcessInteractiveHtml } from '@/packages/@magicclass/generation/src/interactive-post-processor';
import { WidgetMessageChannel } from '@/lib/interactive/widget-message-channel';

// Match the other browser proofs: ordinary unit tests need no browser install.
// INTERACTIVE_LOADING_BROWSER=1 makes a missing Chromium a hard failure.
const browserTest = process.env.INTERACTIVE_LOADING_BROWSER === '1' || existsSync(chromium.executablePath()) ? it : it.skip;

browserTest('paints and initializes a historical interactive page before blocked math CDN resources finish', async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const html = postProcessInteractiveHtml('<html><head></head><body><h1 id="title">Interactive</h1><button id="inc">0</button><p>\\(x^2\\)</p><script>document.addEventListener("DOMContentLoaded", function(){ document.querySelector("#inc").onclick = function(){ this.textContent = "1"; }; });</script></body></html>');
    for (const optimized of [false, true]) {
      const page = await browser.newPage();
      let release!: () => void;
      const held = new Promise<void>((resolve) => { release = resolve; });
      await page.route('https://cdn.jsdelivr.net/**', async (route) => {
        await held;
        const url = route.request().url();
        await route.fulfill({
          contentType: url.endsWith('.css') ? 'text/css' : 'text/javascript',
          body: url.includes('auto-render') ? 'window.renderMathInElement = function(){ document.body.dataset.mathRendered = "yes"; };' : '',
        });
      });
      try {
        await page.setContent('<iframe sandbox="allow-scripts" title="test"></iframe>');
        const requested = page.waitForRequest('https://cdn.jsdelivr.net/**');
        await page.locator('iframe').evaluate((iframe, source) => { (iframe as HTMLIFrameElement).srcdoc = source; }, optimized ? patchHtmlForIframe(html) : html);
        const frame = page.frameLocator('iframe');
        if (optimized) {
          await frame.locator('#title').waitFor({ state: 'visible', timeout: 3000 });
          await frame.locator('#inc').click();
          expect(await frame.locator('#inc').textContent()).toBe('1');
        } else {
          // With the first parser-blocking CDN script held, the body cannot exist.
          await requested;
          expect(await frame.locator('#title').count()).toBe(0);
        }
        await requested;
        release();
        await frame.locator('body[data-math-rendered="yes"]').waitFor({ timeout: 3000 });
      } finally {
        release();
        await page.close();
      }
    }
  } finally {
    await browser.close();
  }
}, 20000);

browserTest('delivers lecture annotations queued before current and historical widgets initialize', async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    for (const legacy of [false, true]) {
      const page = await browser.newPage();
      const posted: Promise<unknown>[] = [];
      const channel = new WidgetMessageChannel((message) => {
        posted.push(page.locator('iframe').evaluate((iframe, data) => {
          (iframe as HTMLIFrameElement).contentWindow!.postMessage(data, '*');
        }, message));
      });
      await page.exposeFunction('widgetReady', () => channel.markReady());
      await page.setContent('<iframe sandbox="allow-scripts"></iframe>');
      await page.evaluate((token) => {
        window.addEventListener('message', (event) => {
          if (event.source !== document.querySelector('iframe')?.contentWindow || event.data.documentToken !== token) return;
          (window as unknown as { widgetReady: () => void }).widgetReady();
        });
      }, channel.token);
      channel.send('HIGHLIGHT_ELEMENT', { target: '#cell', content: '重点' });
      channel.send('ANNOTATE_ELEMENT', { target: '#cell', content: '细胞膜' });
      expect(posted).toHaveLength(0);
      const listener = legacy
        ? 'var type=event.data.action, id=event.data.payload.elementId, text=event.data.payload.text;'
        : 'var type=event.data.type, id=event.data.target.replace(/^#/, ""), text=event.data.content;';
      const html = patchHtmlForIframe(`<html><head></head><body><p id="cell">Cell</p><script>document.addEventListener('DOMContentLoaded', function(){ window.addEventListener('message', function(event){ if(event.source !== window.parent) return; ${listener} var el=document.getElementById(id); if(!el) return; if(type==='HIGHLIGHT_ELEMENT') el.dataset.highlight='yes'; if(type==='ANNOTATE_ELEMENT') el.textContent=text; }); });</script></body></html>`)
        .replace('<script data-iframe-ready-shim>', `<script data-iframe-ready-shim data-document-token="${channel.token}">`);
      await page.locator('iframe').evaluate((iframe, source) => { (iframe as HTMLIFrameElement).srcdoc = source; }, html);
      await page.frameLocator('iframe').locator('#cell[data-highlight="yes"]').waitFor({ timeout: 3000 });
      await Promise.all(posted);
      expect(await page.frameLocator('iframe').locator('#cell').textContent()).toBe('细胞膜');
      await page.close();
    }
  } finally {
    await browser.close();
  }
}, 20000);
