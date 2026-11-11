export function revealSource(id: string) {
  const target = document.getElementById(`source-${id}`);
  if (!target) return;
  let ancestor = target.parentElement;
  while (ancestor) {
    if (ancestor instanceof HTMLDetailsElement) ancestor.open = true;
    ancestor = ancestor.parentElement;
  }
  target.querySelectorAll("details").forEach((detail) => {
    detail.open = true;
  });
  target.focus({ preventScroll: true });
  target.scrollIntoView({ block: "start", behavior: "auto" });
}
