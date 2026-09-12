export interface CastFrame {
  position: number;
  value: number;
  yinYang: "阴" | "阳";
  moving: boolean;
}

export function makeCastTimeline(values: number[]): CastFrame[] {
  if (values.length !== 6 || values.some((value) => ![6, 7, 8, 9].includes(value))) {
    throw new Error("六爻数值必须由六个 6、7、8、9 组成");
  }
  return values.map((value, index) => ({
    position: index + 1,
    value,
    yinYang: value % 2 ? "阳" : "阴",
    moving: value === 6 || value === 9,
  }));
}

export function chooseParticleCount(width: number, averageFrameMs: number): number {
  const normal = width < 600 ? 150 : 220;
  return averageFrameMs > 24 ? Math.floor(normal / 2) : normal;
}
