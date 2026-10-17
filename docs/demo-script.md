# Demo video script (about 7 minutes)

Before recording: `.env` holds an OpenRouter key (see `.env.example`), the database is built,
the dashboard extra is installed, and the terminal font is large. Commands are shown for Windows,
so use `source .venv/bin/activate` on macOS/Linux.

## 1. The problem (0:00 – 0:45)

- LLM summaries of tables tend to round, extrapolate or invent figures.
- Approach: approved SQL only, SQL does the math, every number checked and cited, safe fallback.
- Show the architecture diagram in the README.

## 2. Clean setup (0:45 – 1:30)

```bash
git clone https://github.com/AadityaU/result-explainer.git
cd result-explainer
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,ui]"
python -m result_explainer build-db
python -m result_explainer check
```

- Point out: no API key needed for this, synthetic data from a fixed seed, read-only database.
- Show `.env.example`: the key is the only setting, and the models are chosen automatically.

## 3. Data and approved questions (1:30 – 2:15)

```bash
python -m result_explainer list
python -m result_explainer ask q05 --explainer template --show-sql
```

- Show the header metadata (`columns`, `focus`) and that growth is computed in SQL.
- Note the first month's growth is `n/a` (NULL).

## 4. The dashboard with a real model (2:15 – 4:00)

```bash
python -m result_explainer dashboard
```

- Start on the intro: the four key numbers, then open **How it works** (pipeline diagram,
  validator rules, which model does what) and **Dataset** (tables, diagram, a preview).
- Back on **Explain a question**, pick q03 and click **Explain with the language model** (the
  model only runs on request, which keeps a public deployment's costs down). Read the
  explanation, hover a citation chip to show its value, and point at the **Grounded** badge and
  the "Written by llm (google/gemini-4-argon)" caption. Repeat with q07.
- Show the Cited facts table, then toggle Show SQL and Show all facts.
- Explain the routing: gemini-4-argon drafts, glm-5.3 is the second opinion for a rejected or
  late draft, and why (see `docs/model-evaluation.md`).

## 5. Failure and edge cases (4:00 – 5:15)

- In the dashboard, switch the explainer to **Faulty (failure demo)**: the invented figure and
  "double" are rejected twice, the badge turns to **Fallback** and the attempts are listed.
- Pick q10: empty result, no model is called.
- The same in the terminal: `python -m result_explainer ask q03 --explainer faulty`.

## 6. Evaluation and tests (5:15 – 6:15)

```bash
pytest
```

- Open `docs/model-evaluation.md`: each model's grounded rate and timings, and why Gemini drafts.
- Mention the two bugs the real-model runs found (grouped citations, unbounded response time)
  and the CI badge.

## 7. Decisions and limitations (6:15 – 7:00)

- Open `docs/design-note.md`: no text-to-SQL, deterministic validator, routed models, fallback.
- Be upfront about the limitations: direction words and month names aren't enforced.
