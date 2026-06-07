import { apiFetch } from "../auth/session";
import { apiUrl } from "../config/base";
import type { Program } from "../config/programs";
import { FALLBACK_PROGRAMS } from "../config/programs";

export type HistoryTurn = { role: "user" | "assistant"; content: string };

export type Health = {
  ok: boolean;
  ollama: boolean;
  model: string;
  stt?: string;
  whisper_ready?: boolean;
};

export type ReplyPayload = {
  text: string;
  audio_base64: string;
  audio_mime: string;
};

export async function fetchHealth(): Promise<Health> {
  const r = await apiFetch("api/health");
  if (!r.ok) throw new Error("Backend unreachable");
  return r.json();
}

export async function fetchReply(
  message: string,
  history: HistoryTurn[],
): Promise<ReplyPayload> {
  const r = await apiFetch("api/reply", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || r.statusText);
  }
  return r.json();
}

export type PrewarmStatus = "none" | "pending" | "ready" | "failed";

export type Grade = {
  id: string;
  title: string;
  subtitle?: string;
  stage?: string;
  stage_label?: string;
  semester?: string;
  book?: string;
};

export type Lesson = {
  id: string;
  title: string;
  text: string;
  grade_id?: string;
  unit_num?: number;
  is_builtin?: boolean;
  prewarm_status?: PrewarmStatus;
  prewarm_speed?: number | null;
  prewarm_chunks?: number;
  prewarm_done?: number;
  prewarm_error?: string | null;
  prewarm_program_id?: string | null;
};

export const DEFAULT_GRADE_ID = "kg_middle";

export async function fetchGrades(): Promise<Grade[]> {
  try {
    const r = await apiFetch("api/grades");
    if (!r.ok) return [];
    const data = (await r.json()) as { grades?: Grade[] };
    return data.grades ?? [];
  } catch {
    return [];
  }
}

export async function fetchCustomLessons(
  programId: string,
  ttsSpeed: number,
): Promise<Lesson[]> {
  try {
    const q = new URLSearchParams({
      custom_only: "true",
      program: programId,
      tts_speed: String(ttsSpeed),
    });
    const r = await apiFetch(`api/lessons?${q.toString()}`);
    if (!r.ok) return [];
    const data = (await r.json()) as { lessons?: Lesson[] };
    return data.lessons ?? [];
  } catch {
    return [];
  }
}

export type BuiltinPrewarmStats = {
  scope: string;
  program?: string;
  tts_speed?: number;
  total_lessons?: number;
  ready_lessons?: number;
  pending_lessons?: number;
  failed_lessons?: number;
  waiting_lessons?: number;
  complete?: boolean;
};

export async function fetchBuiltinPrewarmStats(
  programId: string,
  ttsSpeed: number,
): Promise<BuiltinPrewarmStats | null> {
  try {
    const q = new URLSearchParams({
      program: programId,
      tts_speed: String(ttsSpeed),
    });
    const r = await apiFetch(`api/lessons/prewarm/builtin?${q.toString()}`);
    if (!r.ok) return null;
    return (await r.json()) as BuiltinPrewarmStats;
  } catch {
    return null;
  }
}

export async function fetchLessons(
  gradeId: string,
  programId: string,
  ttsSpeed: number,
  options?: { requirePrewarm?: boolean },
): Promise<Lesson[]> {
  try {
    const q = new URLSearchParams({
      grade: gradeId,
      program: programId,
      tts_speed: String(ttsSpeed),
    });
    if (options?.requirePrewarm === false) {
      q.set("require_prewarm", "false");
    }
    const r = await apiFetch(`api/lessons?${q.toString()}`);
    if (!r.ok) return [];
    const data = (await r.json()) as { lessons?: Lesson[] };
    return data.lessons ?? [];
  } catch {
    return [];
  }
}

export async function createLesson(
  title: string,
  text: string,
): Promise<Lesson> {
  const r = await apiFetch("api/lessons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title, text }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || r.statusText);
  }
  const data = (await r.json()) as { lesson: Lesson };
  return data.lesson;
}

export async function deleteLesson(lessonId: string): Promise<void> {
  const r = await apiFetch(`api/lessons/${encodeURIComponent(lessonId)}`, {
    method: "DELETE",
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || r.statusText);
  }
}

export async function prewarmLesson(
  lessonId: string,
  ttsSpeed: number,
  programId: string,
): Promise<void> {
  const r = await apiFetch(
    `api/lessons/${encodeURIComponent(lessonId)}/prewarm`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tts_speed: ttsSpeed, program_id: programId }),
    },
  );
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || r.statusText);
  }
}

export async function fetchPrewarmStatus(
  lessonId: string,
  ttsSpeed: number,
  programId: string,
): Promise<{ ready: boolean; prewarm_status: PrewarmStatus }> {
  const q = new URLSearchParams({
    tts_speed: String(ttsSpeed),
    program: programId,
  });
  const r = await apiFetch(
    `api/lessons/${encodeURIComponent(lessonId)}/prewarm/status?${q.toString()}`,
  );
  if (!r.ok) {
    throw new Error("无法获取预热状态");
  }
  return r.json();
}

export type ActiveCallSession = {
  session_id: string;
  username: string;
  call_started: boolean;
  call_mode: string | null;
  lesson_id: string | null;
  program_id: string | null;
  connected_seconds: number;
};

export type ActiveCallsStats = {
  connected: number;
  calls_started: number;
  read_along_active: number;
  read_along_max: number;
  read_along_full: boolean;
  free_chat_active: number;
  free_chat_max: number;
  free_chat_full: boolean;
  sessions: ActiveCallSession[];
};

export async function fetchActiveCalls(): Promise<ActiveCallsStats> {
  const empty: ActiveCallsStats = {
    connected: 0,
    calls_started: 0,
    read_along_active: 0,
    read_along_max: 2,
    read_along_full: false,
    free_chat_active: 0,
    free_chat_max: 2,
    free_chat_full: false,
    sessions: [],
  };
  try {
    const r = await apiFetch("api/calls/active");
    if (!r.ok) return empty;
    return r.json();
  } catch {
    return empty;
  }
}

export async function fetchPrograms(): Promise<Program[]> {
  try {
    const r = await apiFetch("api/programs");
    if (!r.ok) return FALLBACK_PROGRAMS;
    const data = (await r.json()) as { programs?: Program[] };
    return data.programs?.length ? data.programs : FALLBACK_PROGRAMS;
  } catch {
    return FALLBACK_PROGRAMS;
  }
}
