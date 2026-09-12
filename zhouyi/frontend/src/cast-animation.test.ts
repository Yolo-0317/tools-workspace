import { describe, expect, it } from "vitest";
import { chooseParticleCount, makeCastTimeline } from "./cast-animation";

describe("赛博起卦时间线", () => {
  it("按初爻到上爻生成六个阶段并标出动爻", () => {
    const frames = makeCastTimeline([7, 8, 6, 9, 7, 8]);

    expect(frames.map((frame) => frame.position)).toEqual([1, 2, 3, 4, 5, 6]);
    expect(frames.map((frame) => frame.yinYang)).toEqual([
      "阳", "阴", "阴", "阳", "阳", "阴",
    ]);
    expect(frames.filter((frame) => frame.moving).map((frame) => frame.position)).toEqual([3, 4]);
  });

  it("窄屏或持续低帧率时减少粒子数量", () => {
    expect(chooseParticleCount(1280, 16)).toBe(220);
    expect(chooseParticleCount(390, 16)).toBe(150);
    expect(chooseParticleCount(1280, 28)).toBe(110);
    expect(chooseParticleCount(390, 28)).toBe(75);
  });
});
