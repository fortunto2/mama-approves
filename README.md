# Mama Approves

Point your phone at food. In ~1 second: **✅ APPROVE / ❌ NOPE / 🤔 REVIEW**, a probability, and what mom
would say («Где овощи?»). Built in 50 minutes at the OC AI Builders Lightning Hackathon (Irvine, Oct 21 2026).

How it works: one request to [Jev](https://typesafe.ai), TypeSafe's decision model, with the photo as state and
nine typed questions (home-made? vegetables? junk? portion? expired? allergen? category?). Jev returns
calibrated probabilities, not text. Mom's rules are weights in code. No LLM anywhere.

```bash
export TYPESAFE_API_KEY=...
uv sync
make run F=photo.jpg          # terminal
make serve && make ip         # phone: open the URL in Safari, or wire an iPhone Shortcut to POST /decide
```

Why a decision model and not an LLM: 9 answers in one call, each with confidence; the verdict is a formula you
can tune in a second; and a 0.55 honestly becomes "show me closer" instead of a confident guess.
