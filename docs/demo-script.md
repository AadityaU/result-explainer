# Demo video script (about 7 minutes)

Before recording: `.env` has a working model (see the README), the database is built, and the
terminal font is large. Commands are shown for Windows, so use `source .venv/bin/activate` on macOS/Linux.

## 1. The problem (0:00 – 0:45)

- LLM summaries of tables tend to round, extrapolate or invent figures.
- Approach: approved SQL only, SQL does the math, every number checked and cited, safe fallback.
- Show the architecture diagram in the README.

## 2. Clean setup (0:45 – 1:45)

```bash
git clone https://github.com/AadityaU/result-explainer.git
cd result-explainer
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
python -m result_explainer build-db
python -m result_explainer check
```

- Point out: no API key needed for this, synthetic data from a fixed seed, read-only database.

## 3. Data and approved questions (1:45 – 2:45)

```bash
python -m result_explainer list
python -m result_explainer ask q05 --explainer template --show-sql
```

- Show the header metadata (`columns`, `focus`) and that growth is computed in SQL.
- Note the first month's growth is `n/a` (NULL).

## 4. A grounded model explanation (2:45 – 4:00)

```bash
python -m result_explainer ask q03 --show-facts
python -m result_explainer ask q07
```

- Walk through the fact ids, the explanation's citations and the "Cited facts" legend.
- Status line says `grounded`: every number was matched to a cited fact.

## 5. Failure and edge cases (4:00 – 5:30)

```bash
python -m result_explainer ask q03 --explainer faulty
python -m result_explainer ask q10
```

- Faulty explainer: invented $409,370.31 and "double" are rejected twice, then the template is shown.
- q10: empty result, the model is never called.
- Optional: stop the model server and run `ask q01` to show the endpoint-down fallback.

## 6. Tests (5:30 – 6:15)

```bash
pytest
```

- 124 tests, no network. Mention the validator tests (invented, uncited, wrong row) and the CI badge.

## 7. Decisions and limitations (6:15 – 7:00)

- Open `docs/design-note.md`: no text-to-SQL, deterministic validator, one retry then fallback.
- Be upfront about the limitations: direction words and month names aren't enforced.
