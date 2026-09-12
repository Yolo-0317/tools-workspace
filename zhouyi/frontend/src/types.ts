export interface Topic {
  id: string;
  label: string;
  templates: string[];
}
export interface Question {
  question: string;
  topic: string;
  background: string;
  horizon: string;
  cast_time?: string | null;
  location?: string;
}
export interface CalendarSnapshot {
  input_time?: string | null;
  beijing_time: string;
  timezone?: string;
  year_ganzhi: string;
  month_ganzhi: string;
  day_ganzhi: string;
  hour_ganzhi: string;
  day_stem?: string;
  day_branch?: string;
  month_branch?: string;
  xunkong: string[];
  version: string;
}
export interface NajiaLine {
  position: number;
  yin_yang: "阴" | "阳";
  stem_branch: string;
  element: string;
  relative: string;
  spirit: string;
  moving: boolean;
  flags: string[];
  influences: string[];
}
export interface NajiaChart {
  version: string;
  palace: string;
  palace_element: string;
  palace_stage: string;
  shi_position: number;
  ying_position: number;
  use_candidates: string[];
  selected_use?: string;
  use_selection_version?: string;
  sources?: { book: string; chapters: string[]; source_url: string; verification: string }[];
  original_lines: NajiaLine[];
  changed_lines: NajiaLine[];
  observations: { kind: string; text: string }[];
}
export interface Material {
  id: string;
  role: string;
  book: string;
  edition: string;
  chapter: string;
  text: string;
  source_url: string;
  checksum: string;
  verification: string;
  display_note?: string;
  hexagram_id: number;
  kind: string;
  position: number | null;
}
export interface Paragraph {
  text: string;
  source_ids: string[];
}
export interface Interpretation {
  summary: Paragraph;
  traditional: Paragraph[];
  application: Paragraph;
  actions: Paragraph[];
  citations: { source_id: string; quote: string }[];
}
export interface Attempt {
  id: string;
  status: "running" | "failed" | "succeeded";
  model: string;
  prompt_version: string;
  started_at: string;
  finished_at: string | null;
  result: Interpretation | null;
  error: string | null;
}
export interface Reflection {
  id: string;
  text: string;
  created_at: string;
}
export interface Cast {
  coins?: number[][];
  values: number[];
  moving: number[];
  original_bits: string;
  changed_bits: string;
  original_id: number;
  changed_id: number;
}
export interface Reading {
  id: string;
  request_id: string;
  question: Question;
  cast: Cast;
  selection: {
    version: string;
    reason: string;
    primary: unknown[];
    secondary: unknown[];
  };
  materials: Material[];
  created_at: string;
  interpretations: Attempt[];
  reflections: Reflection[];
  mode?: "classic" | "najia";
  calendar?: CalendarSnapshot | null;
  najia?: NajiaChart | null;
}
export interface ClassicSummary {
  id: number;
  name: string;
  bits: string;
}
export interface Classic extends ClassicSummary {
  judgment: Material;
  lines: Material[];
  use: Material | null;
  tuan: Material;
  xiang: Material;
  xiaoxiang: Material[];
  commentaries: Material[];
}
