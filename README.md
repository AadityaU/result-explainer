# SQL Result Explainer

[![tests](https://github.com/AadityaU/result-explainer/actions/workflows/tests.yml/badge.svg)](https://github.com/AadityaU/result-explainer/actions/workflows/tests.yml)

Explains the results of approved analytics SQL queries in plain language, without inventing numbers.
Every figure in an explanation is checked against the rows the query returned, and every claim
cites the metric it came from.

![Dashboard: a grounded explanation with a citation chip next to every number](docs/images/dashboard-explanation.jpg)

## The problem

Ask a language model to summarise a table and it will often round, extrapolate or invent figures
that sound right but were never in the data. For analytics that is worse than no summary at all.

This project keeps the model on a short leash:

- **SQL does all the math.** Growth rates, shares and averages are computed in the query. The
  model only describes values it is given.
- **Only approved questions run.** Ten curated SQL questions over a synthetic dataset. The model
  never writes SQL, and the database is opened read-only.
- **Every number is verified.** A grounding validator rejects any explanation that contains a
  figure missing from the result, or cites a metric that doesn't hold that figure.
- **Safe fallback.** If the model can't produce a grounded explanation in two attempts, a
  deterministic template explanation is shown instead, clearly marked.

## Try it

There are two ways to use the project. Both run the same pipeline, and both work **without an
API key**: the deterministic template explains instead of the model until you add one (see
[Using a language model](#using-a-language-model)).

**Setup (once, for either way).** Requires Python 3.10+.

```bash
git clone https://github.com/AadityaU/result-explainer.git
cd result-explainer
python -m venv .venv
.venv\Scripts\activate              # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,ui]"          # dev = tests, ui = the Streamlit dashboard
python -m result_explainer build-db
```

### Option A: the dashboard (browser)

```bash
python -m result_explainer dashboard
```

This opens a Streamlit page at http://localhost:8501.

| Tab | What you see |
|-----|--------------|
| **Explain a question** | Pick a question in the sidebar to see its result table, then the explanation. Every number carries a citation chip (hover it to see the cited value) and a badge shows whether the answer was grounded, a fallback, the template or an empty result. A table lists the cited facts. **Show SQL** and **Show all facts** reveal the query and every citable value |
| **How it works** | The pipeline diagram, what the validator rejects, which model does what and why, and the known limitations |
| **Dataset** | Row counts, a diagram of the tables, metric definitions and a preview of any table |
| **Validation check** | Every approved question run and checked in one table |

In the sidebar, the **Explainer** setting switches between the language model, the template and
**Faulty (failure demo)**. Faulty deliberately invents numbers, so you can watch them get
rejected. With a key set, the model only runs when you click **Explain with the language
model**. The page has matching light and dark themes. It follows your system setting, and the
⋮ menu at the top right switches between System, Light and Dark.

### Option B: the command line (terminal)

```bash
python -m result_explainer list                          # the ten approved questions
python -m result_explainer ask q03                       # run one and explain the result
python -m result_explainer ask q05 --show-sql --show-facts
python -m result_explainer ask q03 --explainer faulty    # failure demo: invented numbers rejected
python -m result_explainer ask q10                       # edge case: empty result
python -m result_explainer check                         # validate every approved question
pytest                                                   # the test suite, offline
```

Example output:

```text
$ python -m result_explainer ask q03
q03 | Revenue and average order value by region
How do net revenue and average order value differ across customer regions?

region   delivered_orders  net_revenue  avg_order_value
-------  ----------------  -----------  ---------------
North               1,008  $327,496.25          $324.90
East                  976  $297,743.54          $305.07
South                 883  $276,968.74          $313.67
West                  820  $258,513.97          $315.26
Central               349  $100,843.14          $288.95

Explanation (template - deterministic summary, no model used)
The query returned 5 rows [meta.row_count]. Net revenue peaked at $327,496.25 for North
[r1.net_revenue]. That row also shows delivered orders 1,008 [r1.delivered_orders],
average order value $324.90 [r1.avg_order_value]. The lowest net revenue was $100,843.14
for Central [r5.net_revenue].

Cited facts
  [meta.row_count]                    5  rows returned
  [r1.net_revenue]          $327,496.25  North
  ...
```

## Commands

| Command | What it does |
|---------|--------------|
| `build-db` | Builds `build/store.db` from `sql/schema.sql` and `data/*.csv` |
| `list` | Lists the approved questions |
| `ask <id>` | Runs one approved question and explains the result. Options: `--explainer auto\|template\|llm\|faulty`, `--show-sql`, `--show-facts`, `--db PATH` |
| `dashboard` | Opens the Streamlit dashboard (needs the `ui` extra) |
| `check` | Runs every approved question, checks its columns, and checks that its template explanation passes the validator |
| `evaluate` | Runs every question through each model alone and through the routed pair, and reports how often each stays grounded (`--report PATH` writes markdown) |
| `generate-data` | Rewrites `data/*.csv` from the seeded generator (`--seed`, default 42) |

`--explainer auto` (the default) uses the language model when `LLM_API_KEY` is set, otherwise
the template.

## Using a language model

Copy `.env.example` to `.env` and paste an [OpenRouter](https://openrouter.ai/keys) API key.
That is the only setting. `.env` is gitignored, and nothing in the code holds a key.

**Models are chosen automatically:**

| Role | Model | Why |
|------|-------|-----|
| Draft | `google/gemini-4-argon` | Writes every first answer. Grounded on all 36 evaluated answers (35 on the first attempt), never slower than 13.2 seconds |
| Retry | `z-ai/glm-5.3` | Only called when the draft fails validation (with the validator's issues as feedback) or the draft model errors or misses the 45-second deadline. Just as grounded and about 4× cheaper, but 5 of its 27 answers took over 30 seconds (the slowest 435 s), so it is the second opinion, not the first answer |

The choice comes from [`docs/model-evaluation.md`](docs/model-evaluation.md). To run fully
local instead, point `LLM_BASE_URL` at Ollama and set `LLM_DRAFT_MODEL` / `LLM_RETRY_MODEL`
(see `.env.example`).

A missing key is reported as an error. An unreachable model or an answer that fails both
attempts falls back to the template summary, and the output shows why.

## Deploy

### Streamlit Community Cloud (recommended)

Free hosting made for Streamlit apps, deployed straight from this GitHub repo:

1. Sign in at [share.streamlit.io](https://share.streamlit.io) with the GitHub account that owns
   the repo, and choose **Create app**.
2. Pick the repository `AadityaU/result-explainer`, branch `main`, and main file path
   `src/result_explainer/dashboard.py`.
3. Open **Advanced settings**. Choose Python 3.13, and under **Secrets** paste
   `LLM_API_KEY = "your-openrouter-key"`. Leave the secrets empty to run with the template only.
4. Deploy. Cloud installs [`requirements.txt`](requirements.txt), and the dashboard builds the
   database on its first load.

### Render (alternative)

The repo also includes a Render Blueprint ([`render.yaml`](render.yaml)). In Render, choose
**New > Blueprint**, connect the repo, and paste the key when asked for `LLM_API_KEY`. Render
installs the project, builds the database, starts Streamlit on its port and checks
`/_stcore/health`. Python 3.13 comes from `.python-version`.

| | Streamlit Community Cloud | Render (free plan) |
|---|---|---|
| Setup | Pick the repo and the file, paste the key | Blueprint from `render.yaml` |
| Sleeps after | 12 hours without traffic | 15 minutes without traffic (about a minute to wake) |
| Memory | 690 MB to 2.7 GB | 512 MB |

**Before sharing the link (either host):** a public dashboard spends the key owner's credit. The
dashboard only calls the model when a visitor clicks **Explain with the language model**, and each
visitor session is capped at 20 model explanations. A reload starts a new session, though, so
also set a **credit limit on the OpenRouter key**, and use a key made just for the deployment.

## Architecture

```mermaid
flowchart LR
    Q[Approved question<br/>sql/questions/*.sql] --> SQL[Run SQL<br/>read-only SQLite]
    SQL --> F[Fact table<br/>values + reference ids]
    F -->|no rows| T[Template explainer]
    F --> D[Draft model<br/>gemini-4-argon]
    D --> V1{Grounding<br/>validator}
    V1 -->|pass| OUT[Explanation<br/>with citations]
    V1 -->|fail: issues as feedback| R[Retry model<br/>glm-5.3]
    R --> V2{Grounding<br/>validator}
    V2 -->|pass| OUT
    V2 -->|fail| T
    T --> OUT
```

| Component | File | Role |
|-----------|------|------|
| Approved questions | `sql/questions/`, `questions.py` | One `.sql` file per question with metadata in header comments. The only SQL the app runs |
| Database | `db.py` | Builds SQLite from the CSVs and opens it with `mode=ro` for queries |
| Fact table | `facts.py`, `formatting.py` | Turns rows into referenced values such as `[r1.net_revenue] = $327,496.25` |
| Explainer interface | `explainers/base.py` | One `explain(facts, feedback)` method; only `explainers/llm.py` calls a model |
| Model routing | `explainers/llm.py` | Draft and retry models, OpenRouter by default, any OpenAI-compatible endpoint |
| Grounding validator | `validator.py` | Checks every number and citation against the fact table |
| Pipeline | `pipeline.py` | One attempt per explainer in order, then the template fallback |
| Evaluation | `evaluate.py` | Grounded rate, attempts and latency per model across all questions |
| Dashboard | `dashboard.py` | Streamlit page over the pipeline |

## Data model

A fictional online store's 2025 activity, generated by `src/result_explainer/generate.py` from a
fixed seed (42). All data is synthetic. The same seed always produces byte-identical CSVs, and a
test checks that the committed `data/*.csv` match a fresh generation. The DDL is in
[`sql/schema.sql`](sql/schema.sql).

```mermaid
erDiagram
    customers ||--o{ orders : places
    orders ||--|{ order_items : contains
    products ||--o{ order_items : "sold as"
    order_items ||--o{ returns : "returned as"
    customers {
        int customer_id PK
        text region
        text segment
        text signup_date
    }
    products {
        int product_id PK
        text name
        text category
        int unit_price_cents
    }
    orders {
        int order_id PK
        int customer_id FK
        text order_date
        text channel
        text status
        text ship_date
        text delivery_date
    }
    order_items {
        int order_id PK
        int product_id PK
        int quantity
        int unit_price_cents
        int discount_pct
    }
    returns {
        int return_id PK
        int order_id FK
        int product_id FK
        text return_date
        int quantity
        text reason
    }
```

| Table | Rows | Notes |
|-------|-----:|-------|
| `customers` | 2,500 | region (North, South, East, West, Central) and segment (consumer, business) |
| `products` | 40 | 5 categories × 8 products |
| `orders` | 4,310 | channel (web, mobile, marketplace); cancelled orders have no ship or delivery date |
| `order_items` | 7,515 | price at order time; discount 0, 10 or 20%, heavier in November |
| `returns` | 437 | one row per returned order line; Apparel is returned most often |

Money is stored as integer cents. Queries sum in cents and convert to dollars once, at the end.

**Metric definitions**

- **Net revenue**: quantity × unit price × (100 − discount %) / 100, delivered orders only, before returns.
- **Average order value**: net revenue ÷ delivered orders.
- **Return rate**: units returned ÷ units sold on delivered orders.
- **Repeat customer**: a customer with two or more delivered orders.
- **New customer in a quarter**: the customer's first delivered order falls in that quarter.
- **Delivery days**: days from order date to delivery date.

## Approved questions

Each question is a single SQL file in [`sql/questions/`](sql/questions) with a metadata header:

```sql
-- id: q01
-- title: Monthly revenue and order count
-- question: How did net revenue and the number of delivered orders change month by month in 2025?
-- columns: month=label, delivered_orders=count, net_revenue=currency
-- focus: net_revenue
```

`columns` declares each output column's type (`label`, `count`, `currency`, `percent` or
`number`). The type controls how values are displayed and matched. A result whose columns differ
from the header is refused. `focus` is the main metric the template summary describes.

| id | Question | Rows | Edge case it covers |
|----|----------|-----:|---------------------|
| q01 | Monthly revenue and order count | 12 | time series |
| q02 | Top 10 products by net revenue | 10 | ranking, ties broken by product id |
| q03 | Revenue and average order value by region | 5 | ratio computed in SQL |
| q04 | Revenue share by sales channel | 3 | shares computed in SQL, may not sum to exactly 100 |
| q05 | Month-over-month revenue growth | 12 | the first month's growth is NULL, shown as `n/a` |
| q06 | Repeat-customer rate | 1 | single-row result |
| q07 | Return rate by category | 5 | LEFT JOIN with a zero default |
| q08 | New vs returning customers by quarter | 4 | a real zero: no returning customers in the first quarter |
| q09 | Delivery time by region | 5 | decimal averages |
| q10 | Orders that missed the 14-day delivery promise | 0 | **empty result by design** |

## How grounding works

Every cell of the result becomes a **fact** with a reference id: `r{row}.{column}` (rows start
at 1), plus `meta.row_count`. The explainer sees only these facts and must cite them in square
brackets, one id per bracket or several together (`[r1.net_revenue, r1.delivered_orders]`).
Run `ask <id> --show-facts` to see them all.

The validator ([`validator.py`](src/result_explainer/validator.py)) splits the explanation into
sentences and reports:

| Issue | Meaning |
|-------|---------|
| `invented_number` | A number that matches no value in the result |
| `uncited_number` | A real value, but not held by any fact cited in the same sentence |
| `mismatched_label` | The sentence names a row (e.g. a region) that none of its citations belong to |
| `unsupported_calculation` | Words like *doubled*, *twice* or *3x* that imply math the query didn't do |
| `unknown_reference` | A citation id that doesn't exist |
| `no_citations` | A non-empty result explained without citing anything |
| `empty` | No text at all |

Matching rules:

- A number may be rounded or abbreviated, as long as it is a faithful rounding:
  `$327,496.25` can be written `$327,496` or `$327.5k`, but not `$327k`.
- Signs are compared as absolute values, so "fell 7.5%" can cite `-7.5%`.
- Digits inside labels (`2025-03`, `2025-Q1`) aren't read as numbers. Years from labels and
  numbers from the question itself ("top 10", "14-day") need no citation.
- `n/a` (NULL) values can't back any number.

The pipeline ([`pipeline.py`](src/result_explainer/pipeline.py)) gives the draft model one
attempt. If it is rejected, the retry model gets one attempt, with the validator's issues as
feedback. If the draft model errors, the retry model answers instead. If both fail, the
deterministic template summary is shown. Each answer is labelled:

| Status | Meaning |
|--------|---------|
| `grounded` | A model's answer passed every check (the output names which model) |
| `template` | The template was requested directly (no model) |
| `fallback` | Every attempt was rejected or failed; the template is shown and the rejected attempts are listed |
| `empty` | The query returned no rows, so no model was called |

**Known limitations.** The validator checks numbers, citations and named rows. It does not check
direction words ("rose" vs "fell") or qualitative claims that contain no number or row name. It
also doesn't recognise month names ("March") as the `2025-03` label. These are covered by the
prompt rules, not enforced.

## Failure and edge-case demonstrations

**A model that invents numbers.** The `faulty` explainer inflates a real figure by 25% and adds
a comparison the query never computed. It is rejected on both attempts and the template summary
is shown instead:

```text
$ python -m result_explainer ask q03 --explainer faulty
...
Explanation (fallback - the model's answer was rejected, showing the template summary instead)
The query returned 5 rows [meta.row_count]. Net revenue peaked at $327,496.25 for North
[r1.net_revenue]. ...

Rejected attempts
  1. North led with $409,370.31 [r1.net_revenue], roughly double the next best result.
     - invented_number: $409,370.31 does not appear anywhere in the result
     - unsupported_calculation: "double" implies a calculation the query did not return
  2. ...
```

**An empty result.** q10 returns no rows because every order met the delivery promise. The
model is never called, so it has no chance to fill the gap:

```text
$ python -m result_explainer ask q10
...
(no rows)

Explanation (empty result - nothing to explain, the model was not called)
The query returned 0 rows [meta.row_count], so nothing matched the question "Orders that
missed the 14-day delivery promise".
```

Also covered: NULL growth for the first month in q05 (shown as `n/a`), a model endpoint that is
unreachable (falls back), and a missing API key (clear error, exit code 2). In the dashboard,
choose **Faulty (failure demo)** to see the same rejection with each attempt and its issues.

## Model evaluation

`python -m result_explainer evaluate --report docs/model-evaluation.md` runs every question
through each model alone and through the routed pair. These are real runs against OpenRouter,
counted after the grouped-citation fix described below:

| Setup | Answers | Grounded | First attempt | Median | Slowest |
|-------|--------:|---------:|--------------:|-------:|--------:|
| `google/gemini-4-argon` alone | 27 | 27 | 26 | 6.9 s | 13.2 s |
| `z-ai/glm-5.3` alone | 27 | 27 | 26 | 6.3 s | 435.1 s |
| `z-ai/glm-5.3-flash` alone | 9 | 9 | 8 | 9.6 s | 178.1 s |
| **Routed (what users get)** | 9 | 9 | 9 | 5.6 s | 9.9 s |

The full report, with every explanation and every rejected attempt, is in
[`docs/model-evaluation.md`](docs/model-evaluation.md). The real-model runs found two bugs that
the offline tests had missed:

- **Grouped citations.** Both models often cite several facts in one bracket
  (`[r1.net_revenue, r1.delivered_orders]`), and the validator read those as uncited numbers,
  rejecting answers that were fully grounded.
- **Unbounded response time.** Answers took up to 435 s despite a 120 s timeout, because the
  HTTP timeout only limits the gap between bytes. Every answer now has a hard 45 s deadline.

## Tests

```bash
pytest          # 144 tests, no network needed
python -m result_explainer check
```

| File | Covers |
|------|--------|
| `test_generate.py` | Same seed gives identical bytes; committed CSVs match the generator; data invariants |
| `test_db.py` | Every CSV row loads, foreign keys hold, NULLs survive, read-only connection rejects writes |
| `test_questions.py` | All 10 questions run and return their declared columns; q10 empty; header parsing errors |
| `test_facts.py` | Display formatting, half-up rounding, reference ids, NULL handling |
| `test_validator.py` | Invented, uncited and misattributed numbers; rounding; labels; calculation words |
| `test_template.py` | The template explanation passes the validator for every question |
| `test_llm.py` | Request payload, auth header, errors, settings and model routing, against a mocked endpoint |
| `test_pipeline.py` | Draft then retry model with feedback, fallback, error fall-through, empty results skip the model |
| `test_evaluate.py` | Grounded-rate summary, report contents and the evaluated setups |
| `test_cli.py` | Every command and error path |
| `test_dashboard.py` | Every tab renders; the model waits for a click and stops at the session cap; faulty and empty-result views (Streamlit app tester) |

CI runs `build-db`, `check` and `pytest` from a clean checkout on Python 3.10 and 3.13.

## Project layout

```text
sql/schema.sql                  data model (DDL)
sql/questions/                  the 10 approved questions
data/                           generated sample data (CSV)
src/result_explainer/
  cli.py                        commands
  generate.py                   seeded synthetic data generator
  db.py                         build the database, read-only connections
  questions.py                  question files, registry and runner
  formatting.py  facts.py       displayed values and reference ids
  validator.py                  grounding checks
  explainers/                   base interface, template, llm (with model routing), faulty (demo only)
  pipeline.py                   draft, retry and fallback
  evaluate.py                   model evaluation
  render.py                     terminal output
  dashboard.py                  Streamlit dashboard
tests/                          pytest suite
docs/design-note.md             design and decision note
docs/model-evaluation.md        evaluation report from real model runs
docs/demo-script.md             demo video script
requirements.txt                Streamlit Community Cloud dependencies
render.yaml  .python-version    Render deployment
.streamlit/config.toml          dashboard server settings and light/dark themes
```
