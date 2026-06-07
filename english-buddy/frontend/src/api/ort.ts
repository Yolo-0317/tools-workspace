import { apiFetch } from "../auth/session";

export type OrtPage = {
  index: number;
  lines: string[];
  image: string;
};

export type OrtBook = {
  id: string;
  lesson_id: string;
  title: string;
  ort_level: string;
  book_band: string;
  series: string;
  oxford_owl_free?: boolean;
  page_count: number;
  pages: OrtPage[];
  /** All page images present under frontend/public|dist/ort — required for ORT topic read-along */
  images_ready?: boolean;
};

export type OrtCatalog = {
  version: number | string;
  source: string;
  source_url?: string;
  note?: string;
  image_base: string;
  illustrated_count?: number;
  total_books?: number;
  books: OrtBook[];
};

export async function fetchOrtCatalog(): Promise<OrtCatalog> {
  const r = await apiFetch("api/ort/catalog");
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || r.statusText);
  }
  return r.json();
}
