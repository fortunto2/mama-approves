"""Would mom approve this food? One Jev call on the photo, calibrated answers, code decides.

Jev (TypeSafe AI) looks at the image itself: no captioning LLM in between. Questions are
atomic (is it home-made? is there a vegetable? is it expired?) and the verdict is composed
in code, so mom's rules are weights here, not a prompt. Low confidence falls through to
REVIEW instead of a guess (confidence-gated routing).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from typesafe_sdk import Choice, Image, Noul, Score, TypeSafeClient
from PIL import Image as PILImage, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True  # phone JPEGs and partial downloads: judge what we have
import io

MODEL = os.environ.get("JEV_MODEL", "jev-latest")
IMAGES_HEADER = {"TypeSafe-Danger-Zone-Images": "true"}  # images are "dreamer-ready", opt-in per request
GATE = 0.6  # below this confidence on the main question we ask a human, not mom
MAX_SIDE = 768  # every question that mentions `photo` re-sends the image; 9 copies of a full-size JPEG hit the request limit (400)

# Mom's rules, as weights. Change a number, not a prompt.
RULES = {
    "home_made": 0.25,
    "vegetables": 0.25,
    "warm_meal": 0.15,
    "no_junk": 0.20,
    "portion_ok": 0.15,
}

QUESTIONS = {
    "food_present": Noul(instructions="Is there food or a food product visible in `photo`?"),
    "home_made": Noul(instructions="Does the food in `photo` look home-cooked rather than packaged, fast food or takeout?"),
    "vegetables": Noul(instructions="Are there visible vegetables, greens or fruit in `photo`?"),
    "warm_meal": Noul(instructions="Is the food in `photo` a warm cooked meal (soup, stew, grains, meat with sides) rather than a snack?"),
    "junk": Noul(instructions="Is the food in `photo` junk food: chips, candy, soda, energy drink, deep-fried fast food?"),
    "portion": Score(
        instructions="How big is the portion in `photo` for one adult?",
        criteria=["tiny snack", "small", "normal", "generous", "too much"],
    ),
    "expired": Noul(instructions="If a packaged product with a printed date is visible in `photo`, is that date before 2026-10-21 (expired)?"),
    "allergen": Choice(
        instructions="Which common allergen is most likely present in the food in `photo`?",
        criteria={
            "nuts": "Peanuts or tree nuts visible or typical for this dish",
            "dairy": "Milk, cheese, cream, butter",
            "gluten": "Bread, pasta, pastry, wheat",
            "none": "None of these are visible or typical",
        },
    ),
    "category": Choice(
        instructions="What kind of food is in `photo`?",
        criteria={
            "soup": "Soup or broth",
            "main": "A main dish: meat, fish, grains, pasta with sides",
            "salad": "Salad or raw vegetables",
            "snack": "Chips, bars, pastries, sweets",
            "drink": "A beverage",
            "packaged": "A sealed packaged product",
        },
    ),
}


@dataclass
class Verdict:
    approve: float  # 0..1 composed from mom's rules
    decision: str  # APPROVE | NOPE | REVIEW
    category: str
    allergen: str
    expired: float
    confidence: float
    ms: float
    answers: dict = field(default_factory=dict)

    def mom_says(self) -> str:
        a = self.answers
        if self.decision == "REVIEW":
            return "Покажи поближе, не вижу что это."
        if self.decision == "APPROVE":
            return "Молодец. Но добавки возьми." if a["portion"] <= 1 else "Молодец, ешь."
        lines = []
        if a["junk"] > 0.5:
            lines.append("Это не еда, это химия.")
        if a["vegetables"] < 0.4:
            lines.append("Где овощи?")
        if a["warm_meal"] < 0.4 and a["junk"] <= 0.5:
            lines.append("Горячего поешь.")
        if a["home_made"] < 0.4:
            lines.append("Дома бы приготовил.")
        if self.expired > 0.5:
            lines.append("Это уже просрочено, выбрось.")
        return " ".join(lines) or "Ну такое."


def shrink(photo: Path, max_side: int = MAX_SIDE) -> bytes:
    """JPEG bytes with the long side <= max_side. Jev sees the image once per question, so small wins."""
    im = PILImage.open(photo)
    im = im.convert("RGB")
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def decide(photo: Path, client: TypeSafeClient | None = None) -> Verdict:
    t0 = time.perf_counter()
    own = client is None
    client = client or TypeSafeClient(model=MODEL)
    try:
        r = client.system_one(
            state={"photo": Image(shrink(photo))},
            questions=QUESTIONS,
            extra_headers=IMAGES_HEADER,
        )
    finally:
        if own:
            client.close()
    ms = (time.perf_counter() - t0) * 1000
    n, c, s = r.nouls, r.choices, r.scores
    a = {
        "food_present": n["food_present"].noul,
        "home_made": n["home_made"].noul,
        "vegetables": n["vegetables"].noul,
        "warm_meal": n["warm_meal"].noul,
        "junk": n["junk"].noul,
        "portion": s["portion"].score,
        "expired": n["expired"].noul,
    }
    a["no_junk"] = 1 - a["junk"]
    a["portion_ok"] = 1.0 if 2 <= a["portion"] <= 3 else 0.5 if a["portion"] in (1, 4) else 0.0
    approve = sum(RULES[k] * a[k] for k in RULES)
    if a["expired"] > 0.5:
        approve = min(approve, 0.1)
    conf = c["category"].confidence
    if a["food_present"] < 0.5 or conf < GATE:
        decision = "REVIEW"
    else:
        decision = "APPROVE" if approve >= 0.6 else "NOPE"
    return Verdict(
        approve=round(approve, 2),
        decision=decision,
        category=c["category"].choice,
        allergen=c["allergen"].choice,
        expired=round(a["expired"], 2),
        confidence=round(conf, 2),
        ms=round(ms),
        answers={k: (round(v, 2) if isinstance(v, float) else v) for k, v in a.items()},
    )
