<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import type { Cast } from "../types";
import { chooseParticleCount, makeCastTimeline } from "../cast-animation";

const props = withDefaults(defineProps<{ cast: Cast; durationMs?: number }>(), {
  durationMs: 6000,
});
const emit = defineEmits<{ complete: []; skip: [] }>();
const canvas = ref<HTMLCanvasElement | null>(null);
const completed = ref(0);
const timeline = computed(() => makeCastTimeline(props.cast.values));
const positionNames = ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"];
const currentLabel = computed(() => positionNames[Math.min(completed.value, 5)]);
let animationFrame = 0;
let phaseTimer = 0;
let resizeObserver: ResizeObserver | undefined;
let lastFrame = 0;
let frameTotal = 0;
let frameSamples = 0;

function finish() {
  window.clearInterval(phaseTimer);
  cancelAnimationFrame(animationFrame);
  completed.value = 6;
  emit("complete");
}

function skip() {
  window.clearInterval(phaseTimer);
  cancelAnimationFrame(animationFrame);
  completed.value = 6;
  emit("skip");
}

function resize() {
  const element = canvas.value;
  if (!element) return;
  const ratio = Math.min(window.devicePixelRatio || 1, window.innerWidth < 600 ? 1.5 : 2);
  const box = element.getBoundingClientRect();
  element.width = Math.max(1, Math.floor(box.width * ratio));
  element.height = Math.max(1, Math.floor(box.height * ratio));
}

function draw(time: number) {
  const element = canvas.value;
  const context = element?.getContext("2d");
  if (!element || !context) return;
  if (document.hidden) {
    animationFrame = requestAnimationFrame(draw);
    return;
  }
  if (lastFrame) {
    frameTotal += Math.min(50, time - lastFrame);
    frameSamples += 1;
  }
  lastFrame = time;
  const average = frameSamples ? frameTotal / frameSamples : 16;
  const count = chooseParticleCount(element.clientWidth, average);
  const width = element.width;
  const height = element.height;
  const progress = (time % 1100) / 1100;
  context.clearRect(0, 0, width, height);
  context.globalCompositeOperation = "lighter";
  for (let index = 0; index < count; index += 1) {
    const stream = index % 3;
    const offset = ((index * 47) % count) / count;
    const travel = (progress + offset) % 1;
    const startX = width * (0.18 + stream * 0.32);
    const x = startX + (width * 0.5 - startX) * travel;
    const wave = Math.sin(travel * Math.PI * 2 + index) * width * 0.018 * (1 - travel);
    const y = height * (0.12 + travel * 0.76) + wave;
    const alpha = 0.18 + travel * 0.65;
    context.fillStyle = stream === 2 ? `rgba(190,56,54,${alpha})` : `rgba(93,224,239,${alpha})`;
    context.beginPath();
    context.arc(x, y, Math.max(1, element.width / 900), 0, Math.PI * 2);
    context.fill();
  }
  context.globalCompositeOperation = "source-over";
  animationFrame = requestAnimationFrame(draw);
}

onMounted(() => {
  resize();
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(resize);
    if (canvas.value) resizeObserver.observe(canvas.value);
  }
  const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  if (reduced) {
    completed.value = 6;
    phaseTimer = window.setTimeout(finish, 350);
    return;
  }
  animationFrame = requestAnimationFrame(draw);
  phaseTimer = window.setInterval(() => {
    completed.value += 1;
    if (completed.value >= 6) finish();
  }, props.durationMs / 6);
});

onBeforeUnmount(() => {
  window.clearInterval(phaseTimer);
  window.clearTimeout(phaseTimer);
  cancelAnimationFrame(animationFrame);
  resizeObserver?.disconnect();
});
</script>

<template>
  <section class="cyber-cast" role="status" aria-live="polite">
    <canvas ref="canvas" aria-hidden="true" />
    <div class="cyber-grid" aria-hidden="true" />
    <header>
      <p>信号汇聚 · {{ Math.min(completed + 1, 6) }} / 6</p>
      <h2>{{ completed < 6 ? `正在生成${currentLabel}` : "六爻已生成" }}</h2>
    </header>
    <div class="line-stack">
      <div
        v-for="frame in [...timeline].reverse()"
        :key="frame.position"
        class="cyber-line"
        :class="{
          resolved: frame.position <= completed,
          current: frame.position === completed + 1,
          moving: frame.moving && frame.position <= completed,
          yin: frame.yinYang === '阴',
        }"
        :data-position="frame.position"
      >
        <span class="line-part" /><span v-if="frame.yinYang === '阴'" class="line-part" />
        <small>{{ positionNames[frame.position - 1] }}</small>
      </div>
    </div>
    <button type="button" data-testid="skip-cast-animation" @click="skip">跳过动画</button>
  </section>
</template>

<style scoped>
.cyber-cast {
  --cyan: #67e8f9;
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: grid;
  place-items: center;
  overflow: hidden;
  color: #e8fbff;
  background: radial-gradient(circle at 50% 65%, #123642 0, #071318 34%, #030708 75%);
}
canvas,
.cyber-grid {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}
.cyber-grid {
  opacity: 0.22;
  background-image: linear-gradient(rgba(103, 232, 249, 0.13) 1px, transparent 1px),
    linear-gradient(90deg, rgba(103, 232, 249, 0.13) 1px, transparent 1px);
  background-size: 52px 52px;
  mask-image: radial-gradient(circle, black 20%, transparent 75%);
}
header {
  position: absolute;
  top: clamp(34px, 7vh, 82px);
  z-index: 2;
  text-align: center;
  letter-spacing: 0.12em;
}
header p {
  color: #8db4bd;
}
header h2 {
  margin-top: 8px;
  font-size: clamp(22px, 3vw, 36px);
  font-weight: 400;
}
.line-stack {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  gap: clamp(14px, 2.3vh, 24px);
  width: min(46vw, 420px);
}
.cyber-line {
  position: relative;
  display: flex;
  justify-content: center;
  gap: 13%;
  height: clamp(12px, 1.6vh, 18px);
  opacity: 0.18;
  transition: opacity 350ms ease, transform 350ms ease, filter 350ms ease;
}
.line-part {
  flex: 1;
  max-width: 100%;
  border: 1px solid rgba(103, 232, 249, 0.45);
  background: rgba(103, 232, 249, 0.08);
}
.cyber-line:not(.yin) {
  gap: 0;
}
.cyber-line.resolved {
  opacity: 1;
  filter: drop-shadow(0 0 8px var(--cyan));
}
.cyber-line.resolved .line-part {
  background: linear-gradient(90deg, #dffcff, var(--cyan), #dffcff);
}
.cyber-line.current {
  opacity: 0.6;
  transform: scaleX(1.05);
  animation: scan 900ms ease-in-out infinite alternate;
}
.cyber-line.moving {
  filter: drop-shadow(0 0 10px #be3836);
}
.cyber-line.moving .line-part {
  background: linear-gradient(90deg, #ffd8d2, #be3836, #ffd8d2);
}
.cyber-line small {
  position: absolute;
  left: calc(100% + 18px);
  white-space: nowrap;
  color: #7fa5ae;
  font-size: 12px;
}
button {
  position: absolute;
  z-index: 2;
  bottom: clamp(28px, 6vh, 68px);
  border: 1px solid rgba(103, 232, 249, 0.45);
  padding: 10px 22px;
  color: #bdebf2;
  background: rgba(3, 14, 18, 0.7);
  cursor: pointer;
}
@keyframes scan {
  to { filter: drop-shadow(0 0 14px var(--cyan)); }
}
@media (max-width: 600px) {
  .line-stack { width: 62vw; }
  .cyber-line small { left: calc(100% + 10px); }
}
@media (prefers-reduced-motion: reduce) {
  .cyber-line { transition-duration: 120ms; animation: none; }
  canvas { display: none; }
}
</style>
