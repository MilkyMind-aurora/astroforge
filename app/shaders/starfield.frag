// ============================================================
// AstroForge 星野背景 shader（方案 §1.5 / 星空设计系统规格 §五，MF4）
// 参数（规格 §五参数表即此设计——程序化星野，无逐星 uniform 数组）：
//   uTime     秒；golden test 冻结 0（tokens.starfield.degrade_rule）
//   uSeed     seed.json 的 seed 字段——同种子必同星象（确定性哈希盐，
//             禁每帧随机；TUI/Canvas 降级路径消费同一份坐标列表）
//   uDensity  可见星数（tokens.starfield.density=[60,90]；帧率降级 → 0）
//   uAlphaMax 星点 alpha 上限（夜 0.12 / 昼减半；alpha 三档 0.04/0.08/0.12）
//   uDriftAmp ±2dp 缓漂幅度（归一化坐标）
//   uMeteorT  流星进度 0..1（<0 无流星；间隔 ≥120s / 弹层打开时暂停）
//   uStarColor 星点颜色（palette.ink600 经 lerpPalette 下发——禁硬编码色）
// ============================================================
#version 460 core

#include <flutter/runtime_effect.glsl>

uniform vec2 uSize;
uniform float uTime;
uniform float uSeed;
uniform float uDensity;
uniform float uAlphaMax;
uniform float uDriftAmp;
uniform float uMeteorT;
uniform vec3 uStarColor;

out vec4 fragColor;

const float TAU = 6.28318530718;
const float GRID_COLS = 12.0;
const float GRID_ROWS = 7.0;   // 12×7=84 格 ≥ 密度上限 90 的 1 格 1 星网格

// 确定性哈希（同 uSeed 必同输出；IQ 风格 hash + 种子偏移）
float hash(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z + uSeed * 0.6180339887);
}

vec2 hash2(vec2 p) {
  return vec2(hash(p * 1.37 + 11.7), hash(p * 2.11 + 5.3));
}

// 单格星点：返回该像素收到的 alpha（0 = 无星）
float starAlpha(vec2 cell, vec2 uv, float threshold) {
  float roll = hash(cell * 0.917 + 3.1);
  if (roll >= threshold) {
    return 0.0;                 // 该格无星（密度 = uDensity / 总格数）
  }
  vec2 jitter = hash2(cell);    // 格内抖动位置（0..1）
  vec2 pos = (cell + 0.15 + 0.7 * jitter) / vec2(GRID_COLS, GRID_ROWS);
  // 星等三档 → alpha 档 0.04/0.08/0.12 的比例系数（相对 uAlphaMax）
  float tier = floor(hash(cell * 3.7 + 8.8) * 3.0) * 0.5; // 0 / 0.5 / 1
  float tierBoost = 1.0 + tier * 1.5;                     // 1.0/1.75/2.5
  // ±uDriftAmp 缓漂：4s 周期 + 相位错开（tokens.starfield）
  float phase = jitter.x * TAU;
  pos += vec2(sin(uTime * TAU / 4.0 + phase), cos(uTime * TAU / 5.2 + phase)) * uDriftAmp;
  // 微闪（不改变均值亮度；reduced-motion 时 uTime 冻结 → 静止）
  float twinkle = 0.85 + 0.15 * sin(uTime * 1.7 + phase * 2.0);
  vec2 d = (uv - pos) * vec2(GRID_COLS, GRID_ROWS);
  float dist2 = dot(d, d);
  float radius = 0.22 + tier * 0.06;                       // 格单位半径（对应 1/1.5/2dp）
  float disc = smoothstep(radius, radius * 0.35, sqrt(dist2));
  return disc * clamp(uAlphaMax * tierBoost, 0.0, uAlphaMax) * twinkle;
}

void main() {
  vec2 uv = FlutterFragCoord() / uSize;
  float alpha = 0.0;

  // 密度 → 每格出现概率（12×7 网格覆盖 60~90 颗）
  float threshold = clamp(uDensity / (GRID_COLS * GRID_ROWS), 0.0, 1.0);
  vec2 cell = floor(uv * vec2(GRID_COLS, GRID_ROWS));
  // 漂移会跨格：3×3 邻域各评估一次（每像素 O(1)，与星数无关）
  for (int dy = -1; dy <= 1; dy++) {
    for (int dx = -1; dx <= 1; dx++) {
      alpha += starAlpha(cell + vec2(float(dx), float(dy)), uv, threshold);
    }
  }

  // 流星：路径由 uSeed 推导；uMeteorT∈[0,1] 推进，<0 视为无流星
  if (uMeteorT >= 0.0) {
    vec2 start = vec2(hash(vec2(uSeed, 1.0)), 0.72 + 0.2 * hash(vec2(uSeed, 2.0)));
    vec2 dir = normalize(vec2(0.86, -0.5));
    vec2 head = start + dir * uMeteorT * 0.45;
    vec2 tail = head - dir * 0.055;
    vec2 pa = uv - tail;
    vec2 ba = head - tail;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-5), 0.0, 1.0);
    float dist = length(pa - ba * h);
    float streak = smoothstep(0.006, 0.0, dist);
    float life = sin(3.14159265 * clamp(uMeteorT, 0.0, 1.0));  // 起收笔轻
    alpha += streak * life * uAlphaMax * 2.5;
  }

  fragColor = vec4(uStarColor * min(alpha, 1.0), min(alpha, 1.0));
}
