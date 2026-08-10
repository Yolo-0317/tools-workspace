#!/usr/bin/env python3
"""Interactive terminal chat with Hermes 3 via Ollama."""

from __future__ import annotations

import argparse
import sys

from hermes_client import HermesClient, HermesConfig


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Chat with Hermes 3 through local Ollama.")
    parser.add_argument("--host", default=None, help="Ollama base URL (default: OLLAMA_HOST or 127.0.0.1:11434)")
    parser.add_argument("--model", default=None, help="Model name (default: hermes3:8b)")
    parser.add_argument("--system", default=None, help="System prompt for role / scene setup")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming output")
    parser.add_argument("--message", "-m", default=None, help="Single-turn message; skip REPL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = HermesConfig()
    if args.host:
        config.host = args.host
    if args.model:
        config.model = args.model
    if args.system is not None:
        config.system = args.system

    client = HermesClient(config)
    if not client.ping():
        print(
            f"Cannot reach Ollama at {config.host} or model '{config.model}' is missing.\n"
            f"Run: ollama pull {config.model}",
            file=sys.stderr,
        )
        return 1

    if args.message:
        reply = client.chat(args.message, stream=not args.no_stream)
        if isinstance(reply, str):
            print(reply)
        else:
            for token in reply:
                print(token, end="", flush=True)
            print()
        return 0

    print(f"Model: {config.model} @ {config.host}")
    print("Commands: /reset  /quit")
    print("-" * 40)

    while True:
        try:
            user_text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0

        if not user_text:
            continue
        if user_text in {"/quit", "/exit", "/q"}:
            print("Bye.")
            return 0
        if user_text == "/reset":
            client.reset()
            print("(conversation cleared)")
            continue

        print("\nHermes: ", end="", flush=True)
        reply = client.chat(user_text, stream=not args.no_stream)
        if isinstance(reply, str):
            print(reply)
        else:
            for token in reply:
                print(token, end="", flush=True)
            print()


if __name__ == "__main__":
    raise SystemExit(main())
