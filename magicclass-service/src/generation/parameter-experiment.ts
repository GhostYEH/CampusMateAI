/// <reference lib="dom" />

export const PARAMETER_EXPERIMENT_PROFILE = 'classroom-parameter-experiment/1';

type Token = number | string;

interface Parameter {
  id: string;
  label: string;
  unit: string;
  min: number;
  max: number;
  step: number;
  value: number;
}

interface Preset {
  label: string;
  values: Record<string, number>;
}

export interface ParameterExperiment {
  [key: string]: unknown;
  type: 'simulation';
  nativeRenderer: typeof PARAMETER_EXPERIMENT_PROFILE;
  description: string;
  controls: Parameter[];
  resultLabel: string;
  resultUnit: string;
  expression: Token[];
  chartParameter?: string;
  presets: Preset[];
}

const ID = /^[A-Za-z][A-Za-z0-9_-]{0,31}$/;
const BINARY = ['+', '-', '*', '/', '^'];
const UNARY = ['sqrt', 'abs', 'sin', 'cos'];

export const PARAMETER_EXPERIMENT_GUIDE = [
  '为具有可调参数和可计算结果的普通实验交付 JSON 数据。播放器提供滑块、即时结果和重置。',
  'JSON 包含 description（操作提示与观察目标）、controls（1–6 项）、resultLabel、resultUnit 和 expression（逆波兰表达式）。controls 每项为 {id,label,unit,min,max,step,value}。id 以英文字母开头，只含字母数字下划线连字符，各不相同；数值用真实单位、合理范围和可整除范围的步长。',
  'expression 最多 32 项，只含参数 id、数值和运算符 + - * / ^ sqrt abs sin cos，三角函数用弧度。除数放在 / 之前，例如 ["voltage","resistance","/"] 表示 U/R。保留公式中的单位换算，并保证默认值能得到有限结果。',
  '可选 chartParameter 指定横轴参数 id。可选 presets 列出 0–6 项，每项为 {label,values}，values 的键为要设置的参数 id。使用当前课程的实际内容，说明只写学生要做的操作，不描述界面风格。',
  '涉及模型的空间结构或方向与运动时优先三维模型。需要自定义拖拽、专用仪器或其他非数值行为时使用对应的专用组件。',
].join('\n');

const SAMPLE = {
  description: '固定单位里程能耗，移动滑块观察总能耗如何变化。',
  controls: [{ id: 'distance', label: '里程', unit: 'km', min: 0, max: 20, step: 1, value: 4 }],
  resultLabel: '总能耗', resultUnit: 'Wh', expression: ['distance', 12, '*'], chartParameter: 'distance',
};
export const PARAMETER_EXPERIMENT_EXAMPLE = JSON.stringify(SAMPLE);

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function bounded(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && Math.abs(value) <= 1e8;
}

function label(value: unknown, maxLength: number): string | null {
  return typeof value === 'string' && value.trim().length <= maxLength ? value.trim() : null;
}

function parseParameter(value: unknown): Parameter | null {
  const item = record(value);
  if (!item || typeof item.id !== 'string' || !ID.test(item.id) || item.id === 'constructor') return null;
  const name = label(item.label, 64);
  const unit = label(item.unit, 24);
  const { min, max, step, value: initial } = item;
  if (!name || unit === null || !bounded(min) || !bounded(max) || !bounded(step) || !bounded(initial)) return null;
  if (step <= 0 || max <= min || initial < min || initial > max) return null;
  const count = (max - min) / step;
  if (count < 1 - 1e-7 || count > 2000 + 1e-7 || Math.abs(count - Math.round(count)) > 1e-7) return null;
  return { id: item.id, label: name, unit, min, max, step, value: snapExperimentValue({ min, max, step }, initial) };
}

function snapExperimentValue(parameter: Pick<Parameter, 'min' | 'max' | 'step'>, value: number): number {
  const { min, max, step } = parameter;
  const safe = Math.max(min, Math.min(max, value));
  return Math.min(max, min + Math.round((safe - min) / step) * step);
}

export function parameterExperimentChanges(
  config: ParameterExperiment,
  raw: unknown,
): Record<string, number> | null {
  const values = record(raw);
  if (!values || Object.keys(values).length === 0 || Object.keys(values).length > config.controls.length) return null;
  const changes: Record<string, number> = {};
  for (const [key, value] of Object.entries(values)) {
    const control = config.controls.find((item) => item.id === key);
    if (!control || !bounded(value) || value < control.min || value > control.max) return null;
    changes[key] = snapExperimentValue(control, value);
  }
  return changes;
}

// Self-contained so the sandbox can run exactly the same arithmetic with no network requests.
export function evaluateParameterExperiment(expression: Token[], values: Record<string, number>): number | null {
  const stack: number[] = [];
  for (const token of expression) {
    if (typeof token === 'number' || Object.hasOwn(values, token)) {
      stack.push(typeof token === 'number' ? token : values[token]);
      continue;
    }
    const right = stack.pop();
    if (right === undefined) return null;
    let result: number;
    switch (token) {
      case 'sqrt': result = Math.sqrt(right); break;
      case 'abs': result = Math.abs(right); break;
      case 'sin': result = Math.sin(right); break;
      case 'cos': result = Math.cos(right); break;
      default: {
        const left = stack.pop();
        if (left === undefined) return null;
        switch (token) {
          case '+': result = left + right; break;
          case '-': result = left - right; break;
          case '*': result = left * right; break;
          case '/': result = left / right; break;
          case '^': result = left ** right; break;
          default: return null;
        }
      }
    }
    if (!Number.isFinite(result)) return null;
    stack.push(result);
  }
  return stack.length === 1 && Number.isFinite(stack[0]) ? stack[0] : null;
}

export function materializeParameterExperiment(value: unknown): ParameterExperiment | null {
  const raw = record(value);
  if (!raw || (raw.type !== undefined && raw.type !== 'simulation') ||
      (raw.nativeRenderer !== undefined && raw.nativeRenderer !== PARAMETER_EXPERIMENT_PROFILE)) return null;
  const description = label(raw.description, 960);
  const resultLabel = label(raw.resultLabel, 64);
  const resultUnit = label(raw.resultUnit, 24);
  if (!description || !resultLabel || resultUnit === null) return null;
  if (!Array.isArray(raw.controls) || raw.controls.length < 1 || raw.controls.length > 6) return null;
  const controls: Parameter[] = [];
  for (const candidate of raw.controls) {
    const parameter = parseParameter(candidate);
    if (!parameter || controls.some((item) => item.id === parameter.id) || [...BINARY, ...UNARY].includes(parameter.id)) return null;
    controls.push(parameter);
  }
  const ids = new Set(controls.map((item) => item.id));
  if (!Array.isArray(raw.expression) || raw.expression.length < 1 || raw.expression.length > 32) return null;
  const expression: Token[] = [];
  let usedParameter = false;
  for (const token of raw.expression) {
    if (bounded(token)) expression.push(token);
    else if (typeof token === 'string' && (ids.has(token) || BINARY.includes(token) || UNARY.includes(token))) {
      if (ids.has(token)) usedParameter = true;
      expression.push(token);
    } else return null;
  }
  const initial = Object.fromEntries(controls.map((item) => [item.id, item.value]));
  if (!usedParameter || evaluateParameterExperiment(expression, initial) === null) return null;
  if (raw.chartParameter !== undefined && (typeof raw.chartParameter !== 'string' || !ids.has(raw.chartParameter))) return null;
  if (raw.presets !== undefined && (!Array.isArray(raw.presets) || raw.presets.length > 6)) return null;

  const result: ParameterExperiment = {
    type: 'simulation', nativeRenderer: PARAMETER_EXPERIMENT_PROFILE, description,
    controls, resultLabel, resultUnit, expression,
    ...(typeof raw.chartParameter === 'string' && { chartParameter: raw.chartParameter }),
    presets: [],
  };
  for (const candidate of (raw.presets ?? []) as unknown[]) {
    const preset = record(candidate);
    const name = label(preset?.label, 38);
    const values = parameterExperimentChanges(result, preset?.values);
    if (!name || !values) return null;
    result.presets.push({ label: name, values });
  }
  return result;
}

export function parameterExperimentTargets(config: ParameterExperiment): Set<string> {
  return new Set([
    ...config.controls.map(({ id }) => 'parameter-' + id),
    'experiment-result',
    ...(config.chartParameter ? ['experiment-curve'] : []),
  ]);
}

function mountParameterExperiment(
  evaluate: typeof evaluateParameterExperiment,
  snap: typeof snapExperimentValue,
) {
  const get = (id: string) => document.getElementById(id)!;
  const lab: ParameterExperiment = JSON.parse(get('widget-config').textContent ?? '');
  const isChinese = /[\u3400-\u9fff]/.test(lab.description);
  const copy = (zh: string, en: string) => isChinese ? zh : en;
  document.documentElement.lang = isChinese ? 'zh' : 'en';
  const initial = Object.fromEntries(lab.controls.map((item) => [item.id, item.value]));
  const values = { ...initial };
  const controls = new Map<string, { input: HTMLInputElement; value: HTMLElement }>();
  const valueFormat = new Intl.NumberFormat(isChinese ? 'zh-CN' : 'en', { maximumSignificantDigits: 7, useGrouping: false });
  const format = (n: number) => n === 0 ? '0' : Math.abs(n) < 0.00001 || Math.abs(n) >= 1e8 ? n.toExponential(4) : valueFormat.format(n);
  const output = get('result-value');
  const canvas = get('chart') as HTMLCanvasElement;
  const chartParameter = lab.controls.find((item) => item.id === lab.chartParameter);
  get('description').textContent = lab.description;
  get('result-label').textContent = lab.resultLabel;
  get('axis-label').textContent = chartParameter ? chartParameter.label + (chartParameter.unit ? ' · ' + chartParameter.unit : '') : '';
  get('experiment-curve').hidden = !chartParameter;

  function draw() {
    if (!chartParameter || canvas.clientWidth <= 0) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const width = canvas.clientWidth;
    const height = canvas.clientHeight;
    const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = width * pixelRatio;
    canvas.height = height * pixelRatio;
    ctx.scale(pixelRatio, pixelRatio);
    const inset = 13;
    const samples = Array.from({ length: 81 }, (_, index) => {
      const x = chartParameter.min + (chartParameter.max - chartParameter.min) * index / 80;
      return evaluate(lab.expression, { ...values, [chartParameter.id]: x });
    });
    const finite = samples.filter((v): v is number => v !== null);
    const current = evaluate(lab.expression, values);
    if (current !== null) finite.push(current);
    if (!finite.length) return;
    const min = Math.min(...finite);
    const max = Math.max(...finite);
    const y = (n: number) => height - inset - (height - 2 * inset) * (min === max ? .5 : (n - min) / (max - min));
    ctx.beginPath();
    ctx.strokeStyle = '#415661';
    for (let i = 0; i <= 4; i++) {
      const line = inset + (height - 2 * inset) * i / 4;
      ctx.moveTo(inset, line);
      ctx.lineTo(width - inset, line);
    }
    ctx.stroke();
    ctx.beginPath();
    ctx.strokeStyle = '#add2c8';
    ctx.lineWidth = 2;
    let joined = false;
    for (let i = 0; i < samples.length; i++) {
      const n = samples[i];
      if (n === null) { joined = false; continue; }
      const x = inset + (width - 2 * inset) * i / 80;
      if (joined) ctx.lineTo(x, y(n)); else ctx.moveTo(x, y(n));
      joined = true;
    }
    ctx.stroke();
    if (current !== null) {
      const fraction = (values[chartParameter.id] - chartParameter.min) / (chartParameter.max - chartParameter.min);
      ctx.beginPath();
      ctx.arc(inset + fraction * (width - 2 * inset), y(current), 4, 0, Math.PI * 2);
      ctx.fillStyle = '#dab27a';
      ctx.fill();
    }
  }

  function update() {
    for (const parameter of lab.controls) {
      const field = controls.get(parameter.id)!;
      const n = values[parameter.id];
      field.input.value = String(n);
      const printable = format(n) + (parameter.unit ? ' ' + parameter.unit : '');
      field.value.textContent = printable;
      field.input.setAttribute('aria-valuetext', printable);
    }
    const result = evaluate(lab.expression, values);
    output.textContent = result === null ? copy('当前参数下无定义', 'Undefined for these values') :
      format(result) + (lab.resultUnit ? ' ' + lab.resultUnit : '');
    draw();
  }

  function button(parent: HTMLElement, name: string, apply: () => void) {
    const control = document.createElement('button');
    control.type = 'button';
    control.textContent = name;
    control.onclick = apply;
    parent.appendChild(control);
  }

  for (const parameter of lab.controls) {
    const field = document.createElement('label');
    field.id = 'parameter-' + parameter.id;
    const title = document.createElement('span');
    title.textContent = parameter.label;
    const value = document.createElement('strong');
    const input = document.createElement('input');
    input.type = 'range';
    input.min = String(parameter.min);
    input.max = String(parameter.max);
    input.step = String(parameter.step);
    input.setAttribute('aria-label', parameter.label);
    input.oninput = () => {
      values[parameter.id] = snap(parameter, Number(input.value));
      update();
    };
    field.append(title, value, input);
    get('controls').appendChild(field);
    controls.set(parameter.id, { input, value });
  }
  for (const preset of lab.presets) {
    button(get('buttons'), preset.label, () => { Object.assign(values, initial, preset.values); update(); });
  }
  button(get('buttons'), copy('重置实验', 'Reset'), () => { Object.assign(values, initial); update(); });
  let highlighted: HTMLElement | null = null;
  window.addEventListener('message', (event) => {
    if (event.source !== window.parent) return;
    const data = event.data;
    const type = data?.type ?? data?.action;
    if (type === 'HIGHLIGHT_ELEMENT') {
      const target = data.target ?? data.payload?.elementId;
      if (typeof target !== 'string') return;
      highlighted?.classList.remove('highlight');
      highlighted = document.getElementById(target.replace(/^#/, ''));
      highlighted?.classList.add('highlight');
    } else if (type === 'SET_WIDGET_STATE') {
      const state = data.state ?? data.payload?.state;
      if (!state || typeof state !== 'object') return;
      for (const parameter of lab.controls) {
        const value = state[parameter.id];
        if (typeof value !== 'number' || !Number.isFinite(value)) continue;
        values[parameter.id] = snap(parameter, value);
      }
      update();
    }
  });
  if (chartParameter) new ResizeObserver(draw).observe(canvas);
  update();
}

export function parameterExperimentHtml(config: ParameterExperiment): string {
  const data = JSON.stringify(config).replace(/</g, '\\u003c');
  return `<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
 *{box-sizing:border-box}body{margin:0;background:#142733;color:#f2e9d3;font:16px system-ui,sans-serif}
 main{max-width:860px;margin:auto;padding:14px;display:grid;gap:11px}section,label{border:1px solid #425867;border-radius:10px;padding:10px;background:#192f39}
 p{margin:0;color:#bac8c9;overflow-wrap:anywhere}#controls{display:grid;gap:8px}
 label{display:grid;grid-template-columns:1fr auto;gap:4px}input{grid-column:1/-1;width:100%;min-height:34px;accent-color:#dab27a}
 button{margin:0 8px 6px 0;padding:7px 12px;min-height:44px;border:1px solid #56707a;border-radius:9px;background:#263f48;color:inherit;font:inherit}
 #experiment-result{display:flex;align-items:center;justify-content:space-between;gap:12px}strong{color:#dab27a}
 canvas{display:block;width:100%;height:160px;background:#10212d;border-radius:7px}button:focus-visible,input:focus-visible,.highlight{outline:2px solid #dab27a;outline-offset:1px}
</style></head><body><main>
<p id="description"></p>
<section id="experiment-result"><span id="result-label"></span><strong id="result-value" role="status"></strong></section>
<div id="controls"></div>
<div id="buttons"></div>
<section id="experiment-curve"><canvas id="chart" aria-hidden="true"></canvas><p id="axis-label"></p></section>
</main><script type="application/json" id="widget-config">@DATA@</script>
<script>(@MOUNT@)(@EVALUATE@,@SNAP@);</script>
</body></html>`
    .replace(/@(DATA|MOUNT|EVALUATE|SNAP)@/g, (_, key: 'DATA' | 'MOUNT' | 'EVALUATE' | 'SNAP') => ({
      DATA: data,
      MOUNT: mountParameterExperiment.toString(),
      EVALUATE: evaluateParameterExperiment.toString(),
      SNAP: snapExperimentValue.toString(),
    })[key]);
}
