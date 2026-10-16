"""UserPromptSubmit hook: warn when the conversation gets expensive in tokens.

Reads the transcript, takes the context size of the last assistant turn
(input + cache tokens) and, from WARN_AT of the window on, prints a note that
Claude sees with the user's message, so it tells the owner in the chat (works
in the terminal, the web and the phone app alike) and updates docs/HANDOFF.md.
"""
import json
import os
import sys

WINDOW = int(os.environ.get("ARCHFORGE_CONTEXT_WINDOW", "1000000"))
WARN_AT = 0.70


def context_tokens(path):
    tokens = 0
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                msg = json.loads(line).get("message") or {}
            except ValueError:
                continue
            usage = msg.get("usage") if isinstance(msg, dict) else None
            if msg.get("role") == "assistant" and usage:
                tokens = sum(int(usage.get(k) or 0) for k in
                             ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))
    return tokens


def main():
    try:
        data = json.load(sys.stdin)
        tokens = context_tokens(data["transcript_path"])
    except Exception:
        return 0                       # never block the user's message
    share = tokens / WINDOW
    if share >= WARN_AT:
        print(f"[Έλεγχος tokens] Η συνομιλία έφτασε στο {share:.0%} (~{tokens // 1000}k tokens). "
              "Πες στον ιδιοκτήτη, στην αρχή της απάντησης: «⚠ η συνομιλία έφτασε στο "
              f"{share:.0%} — ενημερώνω το HANDOFF, άλλαξε chat». Ενημέρωσε το docs/HANDOFF.md "
              "(πού σταματήσαμε) και κάνε commit/push πριν από νέα μεγάλη δουλειά.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
