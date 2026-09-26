from pathlib import Path

roots = [
    Path("app/services/brain"),
    Path("app/services"),
]

targets = [
    "conversation",
    "goal",
    "objective",
    "context",
    "constraints",
    "reasoning",
    "decision",
    "planner",
    "prediction",
    "verification",
    "reflection",
    "learning",
]

print("=" * 72)
print("LUMIRA 11.18 — 12-STAGE MODULE OWNERSHIP INSPECTION")
print("=" * 72)
print()

seen = set()

for root in roots:
    if not root.exists():
        continue

    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue

        if path in seen:
            continue

        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lower = text.lower()

        matches = [
            target
            for target in targets
            if target in path.name.lower()
            or target in lower
        ]

        if not matches:
            continue

        seen.add(path)

        print("=" * 72)
        print(f"FILE: {path}")
        print(f"MATCHES: {', '.join(matches)}")
        print("=" * 72)

        print(text)

print()
print("=" * 72)
print("11.18 INSPECTION COMPLETE — NO FILES MODIFIED")
print("=" * 72)
