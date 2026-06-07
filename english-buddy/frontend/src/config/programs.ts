export type CastMember = {
  name_cn: string;
  name_en: string;
  emoji: string;
  avatar: string;
  role: string;
};

export type ProgramTheme = {
  card_bg: string;
  card_border: string;
  accent: string;
  accent2?: string;
};

export type ProgramPage = {
  skin: "girls" | "boys";
  picker_title: string;
  picker_tagline: string;
  picker_bg: string;
  hero_bg: string;
  decor: string[];
  btn_primary: string;
  btn_shadow: string;
  material_hint?: string;
};

export type Program = {
  id: string;
  title: string;
  subtitle: string;
  emoji: string;
  audience: string;
  characters: string[];
  sample_material: string;
  theme: ProgramTheme;
  page: ProgramPage;
  cast: CastMember[];
};

export const FALLBACK_PROGRAMS: Program[] = [
  {
    id: "elsa_snow",
    title: "冰雪艾莎",
    subtitle: "艾莎",
    emoji: "👸",
    audience: "约 4～7 岁",
    characters: ["Elsa"],
    sample_material:
      "Hi! Welcome to the night shadow room.\nHere you can see magical shadows at night.\nWe also have a fun puppet show!",
    theme: {
      card_bg: "linear-gradient(145deg, #fce7f3, #e0e7ff)",
      card_border: "#f9a8d4",
      accent: "#ec4899",
      accent2: "#818cf8",
    },
    page: {
      skin: "girls",
      picker_title: "冰雪艾莎",
      picker_tagline: "艾莎当老师，课文你贴什么就教什么",
      picker_bg:
        "radial-gradient(circle at 20% 15%, #fce7f3 0%, transparent 45%), radial-gradient(circle at 85% 20%, #dbeafe 0%, transparent 40%), linear-gradient(165deg, #fff5f8 0%, #eef2ff 50%, #fdf2f8 100%)",
      hero_bg:
        "radial-gradient(circle at 50% 0%, #fbcfe8 0%, transparent 55%), linear-gradient(180deg, #fff5f8 0%, #eef2ff 100%)",
      decor: [],
      btn_primary: "linear-gradient(135deg, #f472b6, #a78bfa)",
      btn_shadow: "rgba(244, 114, 182, 0.35)",
      material_hint:
        "课文与艾莎剧情无关。下方为场馆导览短文（第1课·夜间光影），也可贴研学/绘本英文。",
    },
    cast: [
      { name_cn: "艾莎", name_en: "Elsa", emoji: "👸", avatar: "elsa", role: "带读老师" },
    ],
  },
  {
    id: "ultra_hero",
    title: "光之奥特曼",
    subtitle: "奥特曼",
    emoji: "🤖",
    audience: "约 7～8 岁（上海二年级）",
    characters: ["Ultra"],
    sample_material:
      "Are you Alice?\nNo, I am Danny.\nI am eight years old.",
    theme: {
      card_bg: "linear-gradient(145deg, #dbeafe, #fef3c7)",
      card_border: "#2563eb",
      accent: "#2563eb",
      accent2: "#f59e0b",
    },
    page: {
      skin: "boys",
      picker_title: "光之奥特曼",
      picker_tagline: "和奥特曼练英文",
      picker_bg:
        "radial-gradient(circle at 15% 10%, #bfdbfe 0%, transparent 42%), radial-gradient(circle at 90% 15%, #fde68a 0%, transparent 38%), linear-gradient(165deg, #eff6ff 0%, #fef9c3 45%, #e0f2fe 100%)",
      hero_bg:
        "radial-gradient(circle at 50% 0%, #93c5fd 0%, transparent 50%), linear-gradient(180deg, #eff6ff 0%, #fef9c3 100%)",
      decor: [],
      btn_primary: "linear-gradient(135deg, #2563eb, #f59e0b)",
      btn_shadow: "rgba(37, 99, 235, 0.35)",
      material_hint:
        "课文与奥特曼剧情无关。下方为沪教二年级「我是 Danny」（第1课），也可贴学校作业英文。",
    },
    cast: [
      { name_cn: "奥特曼", name_en: "Ultra", emoji: "🤖", avatar: "ultra", role: "光之战士" },
    ],
  },
];

export const DEFAULT_PROGRAM_ID = "elsa_snow";

const PROGRAM_ALIASES: Record<string, string> = {
  girls_elsa_judy: "elsa_snow",
  boys_spidey_ultra: "ultra_hero",
  boys_paw_patrol: "ultra_hero",
};

export function getProgramById(
  programs: Program[],
  id: string,
): Program | undefined {
  const mapped = PROGRAM_ALIASES[id] ?? id;
  return programs.find((p) => p.id === mapped);
}
