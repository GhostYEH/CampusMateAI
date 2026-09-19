import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawn } from 'node:child_process';
import type { RenderConfig } from './config.ts';
import type { RenderDocument } from './server.ts';

function text(value: unknown, fallback: string): string {
  const normalized = typeof value === 'string' ? value.replace(/[\u0000-\u001f\u007f]/g, ' ').trim() : '';
  return normalized.slice(0, 200) || fallback;
}

function filterPath(value: string): string {
  return value.replaceAll('\\', '\\\\').replaceAll(':', '\\:').replaceAll(',', '\\,').replaceAll("'", "\\'");
}

function run(command: string, args: string[], timeoutMs: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { stdio: ['ignore', 'ignore', 'pipe'], windowsHide: true });
    let stderr = '';
    child.stderr.on('data', (chunk) => { stderr = `${stderr}${String(chunk)}`.slice(-2000); });
    const timer = setTimeout(() => { child.kill(); reject(new Error('ffmpeg timed out')); }, timeoutMs);
    child.once('error', (error) => { clearTimeout(timer); reject(error); });
    child.once('exit', (code) => {
      clearTimeout(timer);
      if (code === 0) resolve();
      else reject(new Error(`ffmpeg exited with ${code}: ${stderr}`));
    });
  });
}

/** Render a bounded stage to a real H.264 MP4 using the service's local ffmpeg. */
export function createFfmpegRenderer(config: RenderConfig) {
  return async (document: RenderDocument): Promise<Buffer> => {
    const directory = await mkdtemp(join(tmpdir(), 'campusmate-render-'));
    const textFile = join(directory, 'titles.txt');
    const output = join(directory, 'stage.mp4');
    const scenes = Array.isArray(document.scenes) ? document.scenes : [];
    const title = text(document.stage?.name, 'CampusMate 学习内容');
    const sceneTitles = scenes.map((scene, index) => `${index + 1}. ${text(scene?.title, '未命名场景')}`);
    await writeFile(textFile, `${title}\n\n${sceneTitles.join('\n')}`, 'utf8');
    const duration = Math.max(2, Math.min(120, scenes.length * 3));
    try {
      await run(config.ffmpegPath, [
        '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'lavfi', '-i', 'color=c=0x14263d:s=1280x720:r=30',
        '-t', String(duration),
        '-vf', `drawtext=fontcolor=white:fontsize=42:x=(w-text_w)/2:y=(h-text_h)/2:textfile=${filterPath(textFile)}`,
        '-an', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', output,
      ], config.timeoutMs);
      return await readFile(output);
    } finally {
      await rm(directory, { recursive: true, force: true });
    }
  };
}
