"""Shared free-chat opening prompts (Elsa / Ultra / ORT-style themes, round-robin)."""

from __future__ import annotations

# Parenthetical LLM instructions — spoken reply must stay ≤12 words, English only.
FREE_CHAT_KICKOFFS: tuple[str, ...] = (
    "(Free chat.) One-line hello (≤12 words). Ask: What is your name?",
    "(Free chat.) One-line hello (≤12 words). Ask: What is your favorite color?",
    "(Free chat.) One-line hello (≤12 words). Ask: Do you like cats or dogs?",
    "(Free chat.) One-line hello (≤12 words). Ask: Are you happy or sleepy today?",
    "(Free chat.) One-line hello (≤12 words). Ask: What food do you like?",
    "(Free chat.) One-line hello (≤12 words). Ask: Can you say one, two, three?",
    "(Free chat.) One-line hello (≤12 words). Ask: Is it sunny or rainy?",
    "(Free chat.) One-line hello (≤12 words). Ask: What game do you like to play?",
    "(Free chat.) One-line hello (≤12 words). Ask: Who is your favorite hero?",
    "(Free chat.) One-line hello (≤12 words). Ask: Do you like space or the ocean?",
    "(Free chat.) One-line hello (≤12 words). Ask: What sport do you like?",
    "(Free chat.) One-line hello (≤12 words). Ask: Can you run super fast?",
    "(Free chat.) One-line hello (≤12 words). Ask: What is your mission today?",
    "(Free chat.) One-line hello (≤12 words). Ask: Are you ready to learn English?",
    # ORT-style home scenes (original prompts, not ORT book text)
    "(Free chat.) One-line hello (≤12 words). Ask: Are you hungry? Did you eat breakfast?",
    "(Free chat.) One-line hello (≤12 words). Ask: Where is Floppy? Is he in the garden?",
    "(Free chat.) One-line hello (≤12 words). Ask: Shall we go to the park today?",
    "(Free chat.) One-line hello (≤12 words). Ask: Oh no, is it raining? Play inside?",
    "(Free chat.) One-line hello (≤12 words). Ask: What do you want from the shop?",
    "(Free chat.) One-line hello (≤12 words). Ask: What is in the box? What can you see?",
    "(Free chat.) One-line hello (≤12 words). Ask: Where is your toy? Under the chair?",
    "(Free chat.) One-line hello (≤12 words). Ask: Is it bedtime? Are you sleepy?",
    "(Free chat.) One-line hello (≤12 words). Ask: Do you like school? Who is your teacher?",
    "(Free chat.) One-line hello (≤12 words). Ask: Shall we have a picnic? What food?",
    "(Free chat.) One-line hello (≤12 words). Ask: Are your shoes muddy? Let's wash them!",
    "(Free chat.) One-line hello (≤12 words). Ask: Can you help me? Hold the bag, please!",
    # Extra kid-friendly themes
    "(Free chat.) One-line hello (≤12 words). Ask: Do you have a brother or sister?",
    "(Free chat.) One-line hello (≤12 words). Ask: What book do you like to read?",
    "(Free chat.) One-line hello (≤12 words). Ask: Can you sing a little song?",
    "(Free chat.) One-line hello (≤12 words). Ask: What fruit do you like? Apple or banana?",
    "(Free chat.) One-line hello (≤12 words). Ask: Do you go by bus or by car?",
    "(Free chat.) One-line hello (≤12 words). Ask: Can you see the moon tonight?",
    "(Free chat.) One-line hello (≤12 words). Ask: What did you draw today?",
    "(Free chat.) One-line hello (≤12 words). Ask: When is your birthday?",
)

_free_kickoff_cursor = 0


def pick_free_kickoff() -> str:
    """Global round-robin across all free-chat themes (not per teacher)."""
    global _free_kickoff_cursor
    if not FREE_CHAT_KICKOFFS:
        return "(Free chat.) One-line hello. Ask one simple question."
    idx = _free_kickoff_cursor % len(FREE_CHAT_KICKOFFS)
    _free_kickoff_cursor += 1
    return FREE_CHAT_KICKOFFS[idx]
