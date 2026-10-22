"""CLI: mom's verdict on one or more photos.

    uv run python cli/main.py samples/*.jpg
    uv run python cli/main.py photo.jpg --json
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.decide import decide  # noqa: E402

from typesafe_sdk import TypeSafeClient  # noqa: E402


def main(argv: list[str]) -> None:
    as_json = "--json" in argv
    paths = [Path(a) for a in argv if not a.startswith("--")]
    if not paths:
        sys.exit(__doc__)
    with TypeSafeClient() as client:
        for p in paths:
            v = decide(p, client)
            if as_json:
                print(json.dumps({"file": p.name, **v.__dict__, "mom": v.mom_says()}, ensure_ascii=False))
                continue
            mark = {"APPROVE": "✅", "NOPE": "❌", "REVIEW": "🤔"}[v.decision]
            print(f"{mark} {v.decision:7} mom={v.approve:.2f} conf={v.confidence:.2f} {v.ms:4.0f}ms "
                  f"{v.category:8} allergen={v.allergen:6} expired={v.expired:.2f}  {p.name}")
            print(f"   «{v.mom_says()}»")
            print("   " + "  ".join(f"{k}={val}" for k, val in v.answers.items()))


if __name__ == "__main__":
    main(sys.argv[1:])
