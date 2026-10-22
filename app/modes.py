"""Two more judges on top of mom: Bro (two photos, is it a match?) and the recent-verdict gallery."""

from __future__ import annotations

import base64
import io
import time
from collections import deque
from pathlib import Path

from PIL import Image as PILImage
from typesafe_sdk import Choice, Image, Noul, Score, TypeSafeClient

from app.decide import IMAGES_HEADER, shrink

RECENT: deque = deque(maxlen=12)


def thumb(photo: Path, side: int = 160) -> str:
    im = PILImage.open(photo).convert("RGB")
    im.thumbnail((side, side))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def remember(mode: str, photo: Path, verdict: dict, photo2: Path | None = None) -> None:
    RECENT.appendleft({"mode": mode, "t": time.strftime("%H:%M:%S"), "thumb": thumb(photo),
                       "thumb2": thumb(photo2) if photo2 else None, **verdict})


BRO_Q = {
    "same_vibe": Noul(instructions="Do the people in `me` and `them` look like they'd enjoy the same kind of evening?"),
    "both_smiling": Noul(instructions="Are the people in both `me` and `them` smiling or looking friendly?"),
    "style_match": Score(
        instructions="How similar is the overall style (clothes, setting, energy) of `me` and `them`?",
        criteria=["completely different worlds", "different", "some overlap", "similar", "basically twins"],
    ),
    "red_flag": Choice(
        instructions="Biggest red flag visible in `them`, if any",
        criteria={"none": "Nothing alarming", "gym_mirror": "Gym mirror selfie", "car_selfie": "Selfie in a car",
                  "fish": "Holding a fish", "group": "Can't tell which person it is", "filter": "Heavy filters"},
    ),
    "is_person": Noul(instructions="Is there a clearly visible person in `them`?"),
    "friends": Noul(instructions="Judging only by looks, clothes and energy, would the people in `me` and `them` plausibly become friends?"),
    "relationship": Choice(
        instructions="Based on `me` and `them` side by side, which relationship fits best?",
        criteria={
            "partner": "Could be a couple: matching energy, complementary style",
            "best_friend": "Best friends: same humor, same scene",
            "gym_buddy": "Gym or sports buddies: athletic, outdoorsy",
            "coworker": "Coworkers: polite, professional, nothing more",
            "stranger": "Strangers who'd nod at each other once",
        },
    ),
    "dress_match": Score(
        instructions="How well do the clothing styles in `me` and `them` go together?",
        criteria=["clashing", "meh", "fine", "coordinated", "same closet"],
    ),
}


def bro(me: Path, them: Path, client: TypeSafeClient) -> dict:
    t0 = time.perf_counter()
    r = client.system_one(
        state={"me": Image(shrink(me, 640)), "them": Image(shrink(them, 640))},
        questions=BRO_Q, extra_headers=IMAGES_HEADER,
    )
    ms = round((time.perf_counter() - t0) * 1000)
    n, s, c = r.nouls, r.scores, r.choices
    vibe, smile, friends = n["same_vibe"].noul, n["both_smiling"].noul, n["friends"].noul
    style = (s["style_match"].score + s["dress_match"].score) / 8
    flag = c["red_flag"].choice
    rel = c["relationship"].choice
    score = 0.35 * vibe + 0.15 * smile + 0.25 * style + 0.25 * friends
    if flag != "none":
        score *= 0.8
    if n["is_person"].noul < 0.5 or c["red_flag"].confidence < 0.5:
        decision, line = "REVIEW", "Bro can't see them. Get a better pic."
    elif score >= 0.6:
        decision, line = "APPROVE", {"partner": "Bro says go. Text them.", "best_friend": "Bro says: that's your best friend, not your date.",
                                     "gym_buddy": "Bro says: gym buddies. Leg day, not date night.", "coworker": "Bro says: keep it at the office party.",
                                     "stranger": "Bro says go, but you'll have to say hi first."}[rel]
    elif score >= 0.4:
        decision, line = "REVIEW", f"Bro says maybe. Reads as {rel.replace('_', ' ')}. Coffee, not dinner."
    else:
        decision, line = "NOPE", "Bro says nah. Different worlds."
    if flag != "none" and decision != "REVIEW":
        line += f" (Also: {flag.replace('_', ' ')}. Bro noticed.)"
    return {"decision": decision, "approve": round(score, 2), "mom": line, "ms": ms,
            "confidence": round(c["relationship"].confidence, 2), "category": rel.replace("_", " "), "allergen": flag, "expired": 0,
            "answers": {"same_vibe": round(vibe, 2), "friends": round(friends, 2), "both_smiling": round(smile, 2),
                        "style_match": s["style_match"].score, "dress_match": s["dress_match"].score, "red_flag": flag}}


WIFE_Q = {
    "is_item": Noul(instructions="Is there a product or object someone might buy visible in `photo`?"),
    "needed": Noul(instructions="Is the item in `photo` something a household genuinely needs, rather than a toy, gadget or impulse buy?"),
    "gadget": Noul(instructions="Is the item in `photo` a gadget, tool, hobby gear or tech accessory?"),
    "price": Score(
        instructions="How expensive does the item in `photo` look?",
        criteria=["pocket change", "cheap", "moderate", "pricey", "we need to talk"],
    ),
    "garage": Noul(instructions="Does the item in `photo` look like something that ends up unused in a garage or closet within a year?"),
}


def wife(photo: Path, client: TypeSafeClient) -> dict:
    t0 = time.perf_counter()
    r = client.system_one(state={"photo": Image(shrink(photo))}, questions=WIFE_Q, extra_headers=IMAGES_HEADER)
    ms = round((time.perf_counter() - t0) * 1000)
    n, s = r.nouls, r.scores
    needed, gadget, garage = n["needed"].noul, n["gadget"].noul, n["garage"].noul
    price = s["price"].score
    score = 0.5 * needed + 0.3 * (1 - garage) + 0.2 * (1 - price / 4)
    if n["is_item"].noul < 0.6:
        decision, line = "REVIEW", "What is that? Show me properly."
    elif score >= 0.6:
        decision, line = "APPROVE", "Fine. But that's it for this month."
    elif gadget > 0.6 and price >= 3:
        decision, line = "NOPE", "Another gadget? We have one. It's in the garage."
    elif price >= 4:
        decision, line = "NOPE", "We need to talk."
    else:
        decision, line = "NOPE", "Do we really need this? No."
    return {"decision": decision, "approve": round(score, 2), "mom": line, "ms": ms,
            "confidence": round(s["price"].confidence, 2), "category": "purchase", "allergen": "-", "expired": 0,
            "answers": {"needed": round(needed, 2), "gadget": round(gadget, 2), "price": price, "garage": round(garage, 2)}}
