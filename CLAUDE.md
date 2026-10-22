# Mama Approves — would my mom approve this food?

OC AI Builders Lightning Hackathon, Irvine, 21.10.2026 (50-minute build, theme "decision models + LLMs").
Photo of food → **Jev** (TypeSafe AI decision model) looks at the image directly and answers nine atomic
questions with calibrated probabilities → code composes mom's verdict from weights. No LLM in the loop;
low confidence routes to REVIEW instead of guessing.

## Stack

Python 3.13 + uv · `typesafe-sdk` 0.7.5 (`system_one`, `Image`, header `TypeSafe-Danger-Zone-Images: true`
is required for images, they are "dreamer-ready") · FastAPI + uvicorn for the iPhone Shortcut endpoint.
Key: `TYPESAFE_API_KEY` in the environment, never in the repo.

## Map

- `app/decide.py` — questions, mom's rule weights, `decide(photo) -> Verdict`, `mom_says()`
- `app/server.py` — `POST /decide` (multipart `photo`), `GET /` phone-friendly test page
- `cli/main.py` — same pipeline from the terminal, `--json` for machines
- `samples/` — demo photos (gitignored, add your own)

## Commands

`make run F=photo.jpg` · `make serve` · `make ip` (URL for the Shortcut) · `make integration`

## Decisions

- Questions are atomic (home-made? vegetables? junk?) and the verdict is a weighted sum in `RULES`:
  TypeSafe's own guidance, and it means "mom's taste" is numbers, not prompt text.
- `GATE = 0.6` on the category confidence → REVIEW. Expired > 0.5 caps approval at 0.1.
- Dates: the "expired" question hard-codes today's date in the instructions; fine for a demo, not for a product.

## Don't

- Don't add a captioning LLM between the photo and Jev; the point of the demo is that Jev sees the image.
- Don't commit `samples/` with other people's food or faces.
