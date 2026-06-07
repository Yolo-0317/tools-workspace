import type { OrtBook } from "../api/ort";

/** Map a material line index to its page index (0-based). */
export function ortLinePageIndex(book: OrtBook, lineIndex: number): number {
  let acc = 0;
  for (let pi = 0; pi < book.pages.length; pi += 1) {
    const n = book.pages[pi].lines.length;
    if (lineIndex < acc + n) return pi;
    acc += n;
  }
  return Math.max(0, book.pages.length - 1);
}

/** First material line index on a page (0-based). */
export function ortPageFirstLineIndex(book: OrtBook, pageIndex: number): number {
  let acc = 0;
  for (let i = 0; i < pageIndex; i += 1) {
    acc += book.pages[i]?.lines.length ?? 0;
  }
  return acc;
}

/** Material line offset at the start of a page (0-based). */
export function ortPageLineOffset(book: OrtBook, pageIndex: number): number {
  return ortPageFirstLineIndex(book, pageIndex);
}

export function findOrtBook(
  books: OrtBook[],
  idOrLessonId: string,
): OrtBook | undefined {
  return books.find((b) => b.lesson_id === idOrLessonId || b.id === idOrLessonId);
}
