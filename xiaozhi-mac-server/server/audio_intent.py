"""Legacy module — intent routing moved to server.intent_router (LLM-only)."""

from __future__ import annotations

from server.intent_router import RoutedIntent, analyze_user_intent

__all__ = ["RoutedIntent", "analyze_user_intent"]
