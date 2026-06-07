export type OrtLevelFilter = "1" | "1+" | "2" | "3" | "4";

export const DEFAULT_ORT_LEVEL: OrtLevelFilter = "3";

export const ORT_LEVEL_TABS: ReadonlyArray<{
  readonly id: OrtLevelFilter;
  readonly label: string;
}> = [
  { id: "1", label: "Level 1" },
  { id: "1+", label: "Level 1+" },
  { id: "2", label: "Level 2" },
  { id: "3", label: "Level 3" },
  { id: "4", label: "Level 4" },
] as const;

export const ORT_LEVEL_ORDER = ORT_LEVEL_TABS.map((t) => t.id);

export const ORT_GRADE_IDS = [
  "ort_l1",
  "ort_l1plus",
  "ort_l2",
  "ort_l3",
  "ort_l4",
] as const;

export const ORT_GRADE_TO_LEVEL: Record<string, string> = {
  ort_l1: "1",
  ort_l1plus: "1+",
  ort_l2: "2",
  ort_l3: "3",
  ort_l4: "4",
};

export const ORT_LEVEL_TO_GRADE: Record<string, string> = {
  "1": "ort_l1",
  "1+": "ort_l1plus",
  "2": "ort_l2",
  "3": "ort_l3",
  "4": "ort_l4",
};

export function isOrtGrade(gradeId: string): boolean {
  return (ORT_GRADE_IDS as readonly string[]).includes(gradeId);
}

export function ortGradeIdForLevel(level: string): string {
  return ORT_LEVEL_TO_GRADE[level] ?? "ort_l1";
}

export function ortLevelFromGradeId(gradeId: string): string {
  return ORT_GRADE_TO_LEVEL[gradeId] ?? "";
}
