const VERT = `#version 300 es
in vec2 position; void main(){ gl_Position = vec4(position,0.,1.); }`;

const HEAD = `#version 300 es
precision highp float;
out vec4 o;

uniform vec2  uC;
uniform vec2  uHalf;
uniform float uT;
uniform float uHover;
uniform float uPress;
uniform vec4  uRip[3];
uniform vec4  uRipK;
uniform vec4  uRipK2;
uniform vec4  uPtr;
uniform vec4  uPtrK;

#define PI 3.14159265

float sdPill(vec2 p, vec2 b, float r){
  vec2 q = abs(p) - b + r;
  return min(max(q.x,q.y),0.) + length(max(q,0.)) - r;
}

float ripple(vec2 p, float t){
  float sum = 0.;
  for(int i = 0; i < 3; i++){
    if(uRip[i].w < 0.5) continue;
    float age = t - uRip[i].z;
    if(age < 0. || age > 4.) continue;
    vec2  rp = p - uRip[i].xy;
    float facet = 1. + uRipK2.x * cos(uRipK2.y * atan(rp.y, rp.x) + age * 2.1 + float(i) * 2.4);
    float x = (length(rp) - age * uRipK.x * facet) / uRipK.y;
    sum += exp(-pow(abs(x) + 1e-4, uRipK2.z)) * exp(-age * uRipK.z);
  }
  return sum;
}

float pointerW(vec2 p){
  if(uPtr.z < 0.001) return 0.;
  float d = length(p - uPtr.xy) / uPtrK.x;
  return exp(-d*d) * uPtr.z;
}

vec2 pointerWarp(vec2 p){
  float w = pointerW(p);
  if(w <= 0.) return vec2(0.);
  return normalize(p - uPtr.xy + vec2(1e-5)) * w * (uPtrK.y + uPtrK.z * uPtr.w);
}
`;

const FRAG_RIM = HEAD + `
uniform float uBw;
uniform float uE[8];

float perim(vec2 d, float a, float r){
  float P = 4.*a + 2.*PI*r;
  float s;
  if(d.x >= a){
    float th = atan(d.y, d.x - a); if(th < 0.) th += 2.*PI;
    s = (th <= PI*0.5) ? r*th : P - r*(2.*PI - th);
  } else if(d.x <= -a){
    float th = atan(d.y, d.x + a); if(th < 0.) th += 2.*PI;
    s = r*PI*0.5 + 2.*a + r*(th - PI*0.5);
  } else if(d.y >= 0.){
    s = r*PI*0.5 + (a - d.x);
  } else {
    s = r*PI*1.5 + 2.*a + (d.x + a);
  }
  return s / P;
}

float pb(float u, float w){ u = fract(u); float x = min(u, 1.-u); return exp(-(x*x)/(w*w)); }

float rimHot(float s, float t){
  float v = uE[0];
  v += 0.62 * pb(s - t*uE[4],             0.075);
  v += 0.44 * pb(s + t*uE[4]*0.63 + 0.41, 0.135);
  v += 0.30 * pb(s - t*uE[4]*0.34 + 0.73, 0.200);
  return v;
}

float rimBand(float sd, float off){ return 1. - smoothstep(0., uBw*1.05, abs(sd + uBw*0.55 + off)); }

void main(){
  vec2  d  = gl_FragCoord.xy - uC;
  float sd = sdPill(d, uHalf, uHalf.y);
  if(sd > uBw*2.5 || sd < -uBw*3.5){ o = vec4(0.); return; }

  float a = max(uHalf.x - uHalf.y, 0.);
  float s = perim(d, a, uHalf.y);
  float top = mix(1., 0.5 + 0.5 * (d.y / uHalf.y), uE[5]);
  vec2  p   = vec2(d.x, -d.y) / (uHalf.y * 2.);
  float lift = 1. + uPress * uE[6] + ripple(p, uT) * uE[7]
             + pointerW(p) * uPtrK.w;

  o = vec4(vec3(
    rimBand(sd,  uE[2]) * rimHot(s + uE[3], uT),
    rimBand(sd,  0.   ) * rimHot(s,         uT),
    rimBand(sd, -uE[2]) * rimHot(s - uE[3], uT)
  ) * uE[1] * top * lift, 1.);
}`;

const FRAG_SCENE = HEAD + `
uniform float uP[21];

float h21(vec2 p){
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

float vn(vec2 p){
  vec2 i = floor(p), f = fract(p);
  f = f*f*(3.-2.*f);
  float a = h21(i), b = h21(i+vec2(1,0)), c = h21(i+vec2(0,1)), d = h21(i+vec2(1,1));
  return mix(mix(a,b,f.x), mix(c,d,f.x), f.y) * 2. - 1.;
}

float fbm(vec2 p, float g){
  float s = 0., a = 1., n = 0.;
  for(int i=0;i<4;i++){ s += a*vn(p); n += a; p = p*2.03 + 11.7; a *= g; }
  return s / n;
}
float fbm(vec2 p){ return fbm(p, 0.5); }

float wig(float x, float t, float seed){
  return vn(vec2(x,          t*0.150 + seed)) * 0.60
       + vn(vec2(x*2.07 + 4., t*0.105 + seed)) * 0.27
       + vn(vec2(x*4.30 - 7., t*0.080 + seed)) * 0.13;
}

float valleyAt(vec2 p, float t){ return wig(p.x*uP[0], t, 0.0) * uP[1]; }
float densAt  (vec2 p, float t){ return uP[2] * exp(uP[3] * wig(p.x*uP[4] + 9.0, t, 2.7)); }

float surface(vec2 p, float t){
  float V = (p.y - valleyAt(p,t)) * densAt(p,t);
  V += uP[5] * fbm(p*vec2(0.8, 1.7)*uP[6] + vec2(t*0.05, -t*0.03), uP[17]);
  return V - uP[7];
}

float tone(float v){
  float u = fract(v);
  float e = uP[9], W = uP[10] * 0.5;
  return smoothstep(0.5-W-e, 0.5-W, u) * (1. - smoothstep(0.5+W, 0.5+W+e, u));
}

vec3 spec(float t){ return clamp(vec3(1.5) - abs(4.*t - vec3(3.,2.,1.)), 0., 1.); }

void main(){
  vec2  d  = gl_FragCoord.xy - uC;
  float sd = sdPill(d, uHalf, uHalf.y);
  float pill = 1. - smoothstep(-1., 1., sd);
  float S = uHalf.y * 2.;
  float t = uT;

  if(uHover <= 0.0015 || pill <= 0.0015){ o = vec4(0., 0., 0., pill); return; }

  vec2  p = vec2(d.x, -d.y) / S;
  vec2  q = p + pointerWarp(p);
  float h0 = surface(q, t);
  vec2  gp = vec2(dFdx(h0), -dFdy(h0)) * S;
  float V  = surface(q - gp * uP[8] / max(uP[2], .001), t);

  vec2  gd = normalize(gp + vec2(1e-5));
  V += uP[13] * fbm(vec2(dot(q,gd)*uP[14], dot(q, vec2(-gd.y,gd.x))*uP[14]*0.04) + vec2(0., t*0.06));

  float rip  = ripple(p, t);
  float well = pointerW(p);
  V += rip * uRipK.w;

  const int N = 21;
  float mid = 1. - pow(0.5, uP[12]);
  vec3 col = vec3(0.), wsum = vec3(0.);
  for(int i=0;i<N;i++){
    float k = float(i)/float(N-1);
    vec3  w = spec(k);
    col  += w * tone(V + ((1. - pow(1. - k, uP[12])) - mid) * uP[11]);
    wsum += w;
  }
  col /= wsum;
  col = pow(col, vec3(uP[15]));

  float lit = smoothstep(uP[18], uP[19], q.y - valleyAt(q, t));
  lit *= mix(1., lit, 0.55);
  col *= uP[16] * lit;
  col = col * (1. + rip * 1.15 + well * 0.60);

  o = vec4(col * pill * uHover, pill);
}`;

const FRAG_DOWN = `#version 300 es
precision highp float;
out vec4 o;
uniform sampler2D uTex, uTex2;
uniform vec2 uDstTexel;
uniform vec2 uSrcTexel;
uniform float uAdd;
void main(){
  vec2 uv = gl_FragCoord.xy * uDstTexel;
  vec2 e = uDstTexel * 0.25;
  vec4 s = texture(uTex, uv + vec2(-e.x,-e.y)) + texture(uTex, uv + vec2( e.x,-e.y))
         + texture(uTex, uv + vec2(-e.x, e.y)) + texture(uTex, uv + vec2( e.x, e.y));
  s *= 0.25;
  if(uAdd > 0.5){
    vec4 r = texture(uTex2, uv + vec2(-e.x,-e.y)) + texture(uTex2, uv + vec2( e.x,-e.y))
           + texture(uTex2, uv + vec2(-e.x, e.y)) + texture(uTex2, uv + vec2( e.x, e.y));
    s.rgb += r.rgb * 0.25;
  }
  o = s;
}`;

const FRAG_BLUR = `#version 300 es
precision highp float;
out vec4 o;
uniform sampler2D uTex; uniform vec2 uTexel; uniform vec2 uDir; uniform float uR;
void main(){
  vec2 uv = gl_FragCoord.xy * uTexel;
  vec2 st = uTexel * uDir * uR;
  vec4 s = texture(uTex, uv) * 0.1964;
  s += (texture(uTex, uv + st*1.4118) + texture(uTex, uv - st*1.4118)) * 0.2969;
  s += (texture(uTex, uv + st*3.2941) + texture(uTex, uv - st*3.2941)) * 0.0944;
  s += (texture(uTex, uv + st*5.1765) + texture(uTex, uv - st*5.1765)) * 0.0104;
  o = s;
}`;

const FRAG_COMP = HEAD + `
uniform sampler2D uSoft, uRim, uGlow;
uniform vec2  uRes;
uniform float uGlowGain, uGlowIn, uOccl, uDim, uPunch;

void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  vec3 glow = texture(uGlow, uv).rgb;
  vec2  d    = gl_FragCoord.xy - uC;
  float sd   = sdPill(d, uHalf, uHalf.y);
  float pill = 1. - smoothstep(-1., 1., sd);
  vec4 m = texture(uSoft, uv);
  float veil = 1. - smoothstep(0.46, 0.88, abs(d.y) / uHalf.y);
  vec3 metal = pow(max(m.rgb / max(m.a, 1e-3), 0.), vec3(uPunch));
  vec3 core = metal * pill * mix(1., uDim, veil) + texture(uRim, uv).rgb;

  float rip = ripple(vec2(d.x, -d.y) / (uHalf.y * 2.), uT);
  core += vec3(rip * rip) * uRipK2.w * pill * mix(1., 0.42, veil);

  float sdSh = sdPill(d + vec2(0., uHalf.y * 0.62), uHalf * 0.94, uHalf.y * 0.94);
  float occl = uOccl * exp(-max(sdSh, 0.) / (uHalf.y * 0.75));
  vec3 rgb = core + glow * uGlowGain * mix(1., uGlowIn, pill) * (1. - occl * (1. - pill));
  float a = clamp(max(rgb.r, max(rgb.g, rgb.b)), 0., 1.);
  o = vec4(min(rgb, vec3(1.)), a);
}`;

const P = {
  valFreq: 0.50,
  valAmp: 0.55,
  dens: 2.40,
  densVar: 2.20,
  densFreq: 0.32,
  wobAmp: 0.12,
  wobFreq: 1.60,
  lift: 0.05,
  refract: 0.18,
  edge: 0.04,
  width: 0.46,
  disp: 0.30,
  skew: 1.50,
  fineAmp: 0.0,
  fineFreq: 9.0,
  gamma: 1.00,
  gain: 1.90,
  octGain: 0.32,
  litLo: -0.26,
  litHi: 0.10,
  dim: 0.44,
};

const E = {
  base: 0.20,
  hot: 0.82,
  chromA: 0.42,
  chromS: 0.030,
  speed: 0.070,
  top: 0.35,
  press: 0.85,
  ripple: 1.60,
};

const C = {
  glow: 1.95,
  glowR: 1.30,
  glowIn: 0.30,
  occl: 0.62,
  soften: 0.24,
  punch: 1.50,
};

const R = {
  speed: 1.85,
  width: 0.20,
  decay: 1.35,
  amp: 1.35,
  facet: 0.18,
  lobes: 6.0,
  sharp: 1.15,
  emit: 0.45,
  ptrRad: 0.55,
  ptrAmp: 0.32,
  ptrFast: 0.40,
  ptrRim: 0.80,
  ptrLag: 0.0016,
  ptrVref: 4.5,
};

function compileShader(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) || "Liquid-metal shader compilation failed";
    gl.deleteShader(shader);
    throw new Error(message);
  }
  return shader;
}

function createProgram(gl, fragmentSource) {
  const program = gl.createProgram();
  const vertexShader = compileShader(gl, gl.VERTEX_SHADER, VERT);
  const fragmentShader = compileShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.bindAttribLocation(program, 0, "position");
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(program) || "Liquid-metal program linking failed";
    gl.deleteProgram(program);
    throw new Error(message);
  }

  const uniforms = {};
  const uniformCount = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS);
  for (let index = 0; index < uniformCount; index += 1) {
    const info = gl.getActiveUniform(program, index);
    uniforms[info.name.replace("[0]", "")] = gl.getUniformLocation(program, info.name);
  }
  return { program, uniforms };
}

export function mountLiquidMetal(stage) {
  const canvas = stage?.querySelector(".sylva-liquid-fx");
  const button = stage?.querySelector(".sylva-liquid-control");
  if (!canvas || !button || typeof window === "undefined") return () => {};

  let gl;
  try {
    gl = canvas.getContext("webgl2", {
      alpha: true,
      antialias: false,
      premultipliedAlpha: true,
      powerPreference: "high-performance",
    });
  } catch {
    gl = null;
  }

  if (!gl) {
    stage.classList.add("sylva-liquid-fallback");
    return () => {};
  }

  let sceneProgram;
  let rimProgram;
  let downProgram;
  let blurProgram;
  let compositeProgram;
  try {
    sceneProgram = createProgram(gl, FRAG_SCENE);
    rimProgram = createProgram(gl, FRAG_RIM);
    downProgram = createProgram(gl, FRAG_DOWN);
    blurProgram = createProgram(gl, FRAG_BLUR);
    compositeProgram = createProgram(gl, FRAG_COMP);
  } catch (error) {
    console.error(error);
    stage.classList.add("sylva-liquid-fallback");
    return () => {};
  }

  const vao = gl.createVertexArray();
  gl.bindVertexArray(vao);
  const vertexBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, vertexBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(0);
  gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

  const hasFloat = Boolean(gl.getExtension("EXT_color_buffer_half_float"));
  const targets = [];
  const makeTarget = () => {
    const texture = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, texture);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    const framebuffer = gl.createFramebuffer();
    gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
    gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0);
    const target = { texture, framebuffer, width: 0, height: 0 };
    targets.push(target);
    return target;
  };

  const sizeTarget = (target, width, height) => {
    if (target.width === width && target.height === height) return;
    target.width = width;
    target.height = height;
    gl.bindTexture(gl.TEXTURE_2D, target.texture);
    if (hasFloat) {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA16F, width, height, 0, gl.RGBA, gl.HALF_FLOAT, null);
    } else {
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    }
  };

  const coreTarget = makeTarget();
  const rimTarget = makeTarget();
  const softenTargetA = makeTarget();
  const softenTargetB = makeTarget();
  const bloomTargetA = makeTarget();
  const bloomTargetB = makeTarget();

  let renderWidth = 0;
  let renderHeight = 0;
  let buttonWidth = 0;
  let buttonHeight = 0;
  let centerX = 0;
  let centerY = 0;
  let downsample = 4;
  let needsResize = true;
  const glowTextureHeight = 129;

  const resize = () => {
    const canvasRect = canvas.getBoundingClientRect();
    const buttonRect = button.getBoundingClientRect();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(2, Math.round(canvasRect.width * dpr));
    const height = Math.max(2, Math.round(canvasRect.height * dpr));
    if (width !== renderWidth || height !== renderHeight) {
      renderWidth = width;
      renderHeight = height;
      canvas.width = renderWidth;
      canvas.height = renderHeight;
    }
    buttonWidth = buttonRect.width * dpr;
    buttonHeight = buttonRect.height * dpr;
    centerX = (buttonRect.left - canvasRect.left) * dpr + buttonWidth / 2;
    centerY = renderHeight - ((buttonRect.top - canvasRect.top) * dpr + buttonHeight / 2);

    sizeTarget(coreTarget, renderWidth, renderHeight);
    sizeTarget(rimTarget, renderWidth, renderHeight);
    const halfWidth = Math.max(2, Math.ceil(renderWidth / 2));
    const halfHeight = Math.max(2, Math.ceil(renderHeight / 2));
    sizeTarget(softenTargetA, halfWidth, halfHeight);
    sizeTarget(softenTargetB, halfWidth, halfHeight);
    downsample = Math.max(1, Math.min(4, Math.round(buttonHeight / glowTextureHeight)));
    const bloomWidth = Math.max(2, Math.ceil(renderWidth / downsample));
    const bloomHeight = Math.max(2, Math.ceil(renderHeight / downsample));
    sizeTarget(bloomTargetA, bloomWidth, bloomHeight);
    sizeTarget(bloomTargetB, bloomWidth, bloomHeight);
    needsResize = false;
  };

  const drawTo = (target) => {
    gl.bindFramebuffer(gl.FRAMEBUFFER, target?.framebuffer ?? null);
    gl.viewport(0, 0, target?.width ?? renderWidth, target?.height ?? renderHeight);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  };

  const parameterKeys = Object.keys(P);
  const edgeKeys = Object.keys(E);
  const parameterArray = new Float32Array(parameterKeys.length);
  const edgeArray = new Float32Array(edgeKeys.length);
  const rippleSlots = [0, 1, 2].map(() => ({ x: 0, y: 0, time: -99, active: 0 }));
  const rippleArray = new Float32Array(12);
  const pointer = { x: 0, y: 0 };
  const smoothedPointer = { x: 0, y: 0 };
  const interaction = { over: false, press: false, focus: false };
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let rippleIndex = 0;
  let hover = 0;
  let hoverTarget = 0;
  let press = 0;
  let pressTarget = 0;
  let pointerAmount = 0;
  let pointerSpeed = 0;
  let clock = 0;
  let previousTime = performance.now();
  let previousDrawTime = 0;
  let lastStaticSignature = null;
  let animationFrame = null;
  let disposed = false;

  const addRipple = (x, y) => {
    const ripple = rippleSlots[rippleIndex];
    rippleIndex = (rippleIndex + 1) % rippleSlots.length;
    ripple.x = x;
    ripple.y = y;
    ripple.time = clock;
    ripple.active = 1;
  };

  const localPoint = (event) => {
    const bounds = button.getBoundingClientRect();
    const size = Math.max(bounds.height, 1);
    return [
      (event.clientX - (bounds.left + bounds.width / 2)) / size,
      (event.clientY - (bounds.top + bounds.height / 2)) / size,
    ];
  };

  const syncInteraction = () => {
    hoverTarget = interaction.over || interaction.press || interaction.focus ? 1 : 0;
    pressTarget = interaction.press ? 1 : 0;
    stage.classList.toggle("hot", hoverTarget > 0.5);
    stage.classList.toggle("press", interaction.press);
  };

  const drawFrame = (now) => {
    if (disposed) return;
    const rawDelta = (now - previousTime) / 1000;
    previousTime = now;
    const delta = Math.min(rawDelta, 1 / 20);
    if (!reducedMotion.matches) clock += delta;

    const hoverEase = hoverTarget > hover
      ? 1 - Math.pow(0.0012, delta)
      : 1 - Math.pow(0.00012, delta);
    hover += (hoverTarget - hover) * hoverEase;
    if (Math.abs(hoverTarget - hover) < 0.0008) hover = hoverTarget;

    const pressEase = pressTarget > press
      ? 1 - Math.pow(1e-9, delta)
      : 1 - Math.pow(0.004, delta);
    press += (pressTarget - press) * pressEase;
    if (Math.abs(pressTarget - press) < 0.002) press = pressTarget;

    rippleSlots.forEach((ripple, index) => {
      if (ripple.active && clock - ripple.time > 4) ripple.active = 0;
      rippleArray[index * 4] = ripple.x;
      rippleArray[index * 4 + 1] = ripple.y;
      rippleArray[index * 4 + 2] = ripple.time;
      rippleArray[index * 4 + 3] = ripple.active;
    });
    const rippleIsLive = rippleSlots.some((ripple) => ripple.active);

    const lag = 1 - Math.pow(R.ptrLag, delta);
    const deltaX = (pointer.x - smoothedPointer.x) * lag;
    const deltaY = (pointer.y - smoothedPointer.y) * lag;
    smoothedPointer.x += deltaX;
    smoothedPointer.y += deltaY;
    const instantSpeed = Math.min(
      Math.hypot(deltaX, deltaY) / Math.max(delta, 1e-3) / R.ptrVref,
      1,
    );
    pointerSpeed += (instantSpeed - pointerSpeed)
      * (1 - Math.pow(instantSpeed > pointerSpeed ? 0.001 : 0.02, delta));
    const desiredWell = interaction.over || interaction.press ? 1 : 0;
    pointerAmount += (desiredWell - pointerAmount) * (1 - Math.pow(0.004, delta));
    if (Math.abs(desiredWell - pointerAmount) < 0.002) pointerAmount = desiredWell;

    if (needsResize) resize();

    const staticSignature = reducedMotion.matches && !rippleIsLive && pointerAmount < 0.002
      ? `${hover}|${press}|${renderWidth}|${renderHeight}`
      : null;
    if (staticSignature !== null && staticSignature === lastStaticSignature) {
      animationFrame = window.requestAnimationFrame(drawFrame);
      return;
    }
    lastStaticSignature = staticSignature;

    const idle = !interaction.over && !interaction.press && !interaction.focus
      && !rippleIsLive && hover < 0.002 && press < 0.002 && pointerAmount < 0.002;
    if (idle && now - previousDrawTime < 1000 / 30) {
      animationFrame = window.requestAnimationFrame(drawFrame);
      return;
    }
    previousDrawTime = now;

    parameterKeys.forEach((key, index) => { parameterArray[index] = P[key]; });
    edgeKeys.forEach((key, index) => { edgeArray[index] = E[key]; });
    const rimWidth = Math.max(1.5, 3.2 * (buttonHeight / 516));

    gl.useProgram(sceneProgram.program);
    gl.uniform2f(sceneProgram.uniforms.uC, centerX, centerY);
    gl.uniform2f(sceneProgram.uniforms.uHalf, buttonWidth / 2, buttonHeight / 2);
    gl.uniform1f(sceneProgram.uniforms.uT, clock);
    gl.uniform1f(sceneProgram.uniforms.uHover, hover);
    gl.uniform1f(sceneProgram.uniforms.uPress, press);
    gl.uniform4fv(sceneProgram.uniforms.uRip, rippleArray);
    gl.uniform4f(sceneProgram.uniforms.uRipK, R.speed, R.width, R.decay, R.amp);
    gl.uniform4f(sceneProgram.uniforms.uRipK2, R.facet, R.lobes, R.sharp, R.emit);
    gl.uniform4f(sceneProgram.uniforms.uPtr, smoothedPointer.x, smoothedPointer.y, pointerAmount, pointerSpeed);
    gl.uniform4f(sceneProgram.uniforms.uPtrK, R.ptrRad, R.ptrAmp, R.ptrFast, R.ptrRim);
    gl.uniform1fv(sceneProgram.uniforms.uP, parameterArray);
    drawTo(coreTarget);

    gl.useProgram(rimProgram.program);
    gl.uniform2f(rimProgram.uniforms.uC, centerX, centerY);
    gl.uniform2f(rimProgram.uniforms.uHalf, buttonWidth / 2, buttonHeight / 2);
    gl.uniform1f(rimProgram.uniforms.uT, clock);
    gl.uniform1f(rimProgram.uniforms.uBw, rimWidth);
    gl.uniform1f(rimProgram.uniforms.uPress, press);
    gl.uniform4fv(rimProgram.uniforms.uRip, rippleArray);
    gl.uniform4f(rimProgram.uniforms.uRipK, R.speed, R.width, R.decay, R.amp);
    gl.uniform4f(rimProgram.uniforms.uRipK2, R.facet, R.lobes, R.sharp, R.emit);
    gl.uniform4f(rimProgram.uniforms.uPtr, smoothedPointer.x, smoothedPointer.y, pointerAmount, pointerSpeed);
    gl.uniform4f(rimProgram.uniforms.uPtrK, R.ptrRad, R.ptrAmp, R.ptrFast, R.ptrRim);
    gl.uniform1fv(rimProgram.uniforms.uE, edgeArray);
    drawTo(rimTarget);

    gl.useProgram(downProgram.program);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, coreTarget.texture);
    gl.uniform1i(downProgram.uniforms.uTex, 0);
    gl.uniform1f(downProgram.uniforms.uAdd, 0);
    gl.uniform2f(downProgram.uniforms.uDstTexel, 1 / softenTargetA.width, 1 / softenTargetA.height);
    gl.uniform2f(downProgram.uniforms.uSrcTexel, 1 / renderWidth, 1 / renderHeight);
    drawTo(softenTargetA);

    gl.useProgram(blurProgram.program);
    gl.uniform1i(blurProgram.uniforms.uTex, 0);
    gl.uniform2f(blurProgram.uniforms.uTexel, 1 / softenTargetA.width, 1 / softenTargetA.height);
    const softenSigma = C.soften * (buttonHeight * 0.5) * 0.95;
    if (softenSigma > 0.1) {
      const iterations = Math.min(4, Math.max(1, Math.ceil(softenSigma / 3.0)));
      gl.uniform1f(blurProgram.uniforms.uR, softenSigma / Math.sqrt(iterations) / 1.95);
      for (let index = 0; index < iterations; index += 1) {
        gl.bindTexture(gl.TEXTURE_2D, softenTargetA.texture);
        gl.uniform2f(blurProgram.uniforms.uDir, 1, 0);
        drawTo(softenTargetB);
        gl.bindTexture(gl.TEXTURE_2D, softenTargetB.texture);
        gl.uniform2f(blurProgram.uniforms.uDir, 0, 1);
        drawTo(softenTargetA);
      }
    }

    gl.useProgram(downProgram.program);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, softenTargetA.texture);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, rimTarget.texture);
    gl.uniform1i(downProgram.uniforms.uTex, 0);
    gl.uniform1i(downProgram.uniforms.uTex2, 1);
    gl.uniform1f(downProgram.uniforms.uAdd, 1);
    gl.uniform2f(downProgram.uniforms.uDstTexel, 1 / bloomTargetA.width, 1 / bloomTargetA.height);
    gl.uniform2f(downProgram.uniforms.uSrcTexel, 1 / softenTargetA.width, 1 / softenTargetA.height);
    drawTo(bloomTargetA);

    gl.useProgram(blurProgram.program);
    gl.activeTexture(gl.TEXTURE0);
    gl.uniform1i(blurProgram.uniforms.uTex, 0);
    gl.uniform2f(blurProgram.uniforms.uTexel, 1 / bloomTargetA.width, 1 / bloomTargetA.height);
    const glowRadius = C.glowR * (buttonHeight / downsample) / glowTextureHeight;
    [1.0, 2.3, 5.2, 9.0].forEach((radius) => {
      gl.uniform1f(blurProgram.uniforms.uR, radius * glowRadius);
      gl.bindTexture(gl.TEXTURE_2D, bloomTargetA.texture);
      gl.uniform2f(blurProgram.uniforms.uDir, 1, 0);
      drawTo(bloomTargetB);
      gl.bindTexture(gl.TEXTURE_2D, bloomTargetB.texture);
      gl.uniform2f(blurProgram.uniforms.uDir, 0, 1);
      drawTo(bloomTargetA);
    });

    gl.useProgram(compositeProgram.program);
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, softenTargetA.texture);
    gl.uniform1i(compositeProgram.uniforms.uSoft, 0);
    gl.activeTexture(gl.TEXTURE1);
    gl.bindTexture(gl.TEXTURE_2D, rimTarget.texture);
    gl.uniform1i(compositeProgram.uniforms.uRim, 1);
    gl.activeTexture(gl.TEXTURE2);
    gl.bindTexture(gl.TEXTURE_2D, bloomTargetA.texture);
    gl.uniform1i(compositeProgram.uniforms.uGlow, 2);
    gl.uniform2f(compositeProgram.uniforms.uRes, renderWidth, renderHeight);
    gl.uniform2f(compositeProgram.uniforms.uC, centerX, centerY);
    gl.uniform2f(compositeProgram.uniforms.uHalf, buttonWidth / 2, buttonHeight / 2);
    gl.uniform1f(compositeProgram.uniforms.uT, clock);
    gl.uniform4fv(compositeProgram.uniforms.uRip, rippleArray);
    gl.uniform4f(compositeProgram.uniforms.uRipK, R.speed, R.width, R.decay, R.amp);
    gl.uniform4f(compositeProgram.uniforms.uRipK2, R.facet, R.lobes, R.sharp, R.emit);
    gl.uniform1f(compositeProgram.uniforms.uGlowGain, C.glow);
    gl.uniform1f(compositeProgram.uniforms.uGlowIn, C.glowIn);
    gl.uniform1f(compositeProgram.uniforms.uOccl, C.occl);
    gl.uniform1f(compositeProgram.uniforms.uDim, P.dim);
    gl.uniform1f(compositeProgram.uniforms.uPunch, C.punch);
    drawTo(null);

    animationFrame = window.requestAnimationFrame(drawFrame);
  };

  const handlePointerEnter = (event) => {
    if (event.pointerType !== "mouse") return;
    [pointer.x, pointer.y] = localPoint(event);
    smoothedPointer.x = pointer.x;
    smoothedPointer.y = pointer.y;
    pointerSpeed = 0;
    interaction.over = true;
    syncInteraction();
  };
  const handlePointerLeave = (event) => {
    if (event.pointerType === "mouse") {
      interaction.over = false;
      syncInteraction();
    }
  };
  const handlePointerMove = (event) => {
    if (!interaction.over && !interaction.press) return;
    [pointer.x, pointer.y] = localPoint(event);
  };
  const handlePointerDown = (event) => {
    [pointer.x, pointer.y] = localPoint(event);
    interaction.press = true;
    syncInteraction();
    addRipple(pointer.x, pointer.y);
  };
  const handlePointerUp = () => {
    interaction.press = false;
    syncInteraction();
  };
  const handleFocus = () => {
    interaction.focus = button.matches(":focus-visible");
    syncInteraction();
  };
  const handleBlur = () => {
    interaction.focus = false;
    syncInteraction();
  };
  const handleKeyDown = (event) => {
    if ((event.key !== "Enter" && event.key !== " ") || event.repeat) return;
    interaction.press = true;
    syncInteraction();
    addRipple(0, 0);
  };
  const handleKeyUp = (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    interaction.press = false;
    syncInteraction();
  };
  const handleMotionChange = () => {
    lastStaticSignature = null;
  };

  button.addEventListener("pointerenter", handlePointerEnter);
  button.addEventListener("pointerleave", handlePointerLeave);
  button.addEventListener("pointerdown", handlePointerDown);
  button.addEventListener("focus", handleFocus);
  button.addEventListener("blur", handleBlur);
  button.addEventListener("keydown", handleKeyDown);
  button.addEventListener("keyup", handleKeyUp);
  window.addEventListener("pointermove", handlePointerMove, { passive: true });
  window.addEventListener("pointerup", handlePointerUp);
  window.addEventListener("pointercancel", handlePointerUp);
  reducedMotion.addEventListener?.("change", handleMotionChange);

  const resizeObserver = new ResizeObserver(() => { needsResize = true; });
  resizeObserver.observe(stage);
  resize();
  animationFrame = window.requestAnimationFrame(drawFrame);

  return () => {
    disposed = true;
    if (animationFrame !== null) window.cancelAnimationFrame(animationFrame);
    resizeObserver.disconnect();
    button.removeEventListener("pointerenter", handlePointerEnter);
    button.removeEventListener("pointerleave", handlePointerLeave);
    button.removeEventListener("pointerdown", handlePointerDown);
    button.removeEventListener("focus", handleFocus);
    button.removeEventListener("blur", handleBlur);
    button.removeEventListener("keydown", handleKeyDown);
    button.removeEventListener("keyup", handleKeyUp);
    window.removeEventListener("pointermove", handlePointerMove);
    window.removeEventListener("pointerup", handlePointerUp);
    window.removeEventListener("pointercancel", handlePointerUp);
    reducedMotion.removeEventListener?.("change", handleMotionChange);
    targets.forEach((target) => {
      gl.deleteFramebuffer(target.framebuffer);
      gl.deleteTexture(target.texture);
    });
    gl.deleteBuffer(vertexBuffer);
    gl.deleteVertexArray(vao);
    [sceneProgram, rimProgram, downProgram, blurProgram, compositeProgram]
      .forEach(({ program }) => gl.deleteProgram(program));
  };
}
