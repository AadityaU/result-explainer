# Project Breakdown: SQL Result Explainer

Welcome to **SQL Result Explainer**! This guide explains everything about this project in simple English — what it is, why it exists, how data flows through it step-by-step, the database queries and APIs it uses, and real code snippets showing how each piece works under the hood.

---

## 1. What Is This Project?

### The Problem
Large Language Models (LLMs) are great at writing human-sounding text, but they have a fatal flaw: **they hallucinate numbers**. When summarizing business reports or SQL query results, an LLM might turn `$327,450` into `$350,000` or invent a growth rate out of thin air. In business analytics, finance, or executive reporting, **hallucinated numbers can lead to disastrous decisions**.

### The Solution
**SQL Result Explainer** is a Python tool that generates natural language explanations for SQL query results with a **zero-hallucination guarantee**:
1. It executes an analytical SQL query against a local SQLite database in strict **read-only mode**.
2. It converts the table of numbers into a structured **Fact Table** where each cell has a unique coordinate (like `r1.net_revenue = $327k`).
3. An LLM drafts an explanation and **must cite every number** using brackets, like `[r1.net_revenue]`.
4. A deterministic **Validator** checks every single number in the text against the Fact Table.
5. If the LLM makes an error (hallucinates, drops a citation, or mislabels a value), the system feeds the exact validator error back to a second LLM to fix it.
6. If the second attempt still fails, it automatically falls back to a **deterministic template**, guaranteeing that the user **never sees an inaccurate number**.

---

## 2. Requirements & Tech Stack

### System Requirements
- **Python**: 3.10 or higher
- **Database**: SQLite 3 (built-in with Python, used via URI `?mode=ro` for read-only safety)
- **API Key**: An [OpenRouter](https://openrouter.ai/) API key for LLM generation (stored in `.env` as `LLM_API_KEY`)

### Key Dependencies (`requirements.txt`)
- `httpx` (>=0.27.0): Handles fast, streaming HTTP requests to the OpenRouter LLM API.
- `python-dotenv` (>=1.0.0): Loads the API key and configuration from `.env`.
- `streamlit` (>=1.35.0): Provides the interactive web dashboard.
- `pytest` (>=8.0.0): Runs the offline test suite (140 tests).

---

## 3. High-Level Architecture & Flow

Here is how data moves through the application from start to finish:

```
+-------------------------------------------------------------------------------+
|                             User (CLI or Streamlit)                           |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 1. Question Loader (questions.py)                                             |
|    - Parses SQL file header metadata (-- id, -- title, -- columns, etc.)       |
|    - Connects to SQLite in read-only mode (?mode=ro)                          |
|    - Runs SQL query -> Returns QueryResult (columns + rows)                   |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 2. Fact Table Builder (facts.py)                                              |
|    - Turns raw rows into Fact objects with reference tags                     |
|    - Example: r1.net_revenue = $327k (exact: 327450.0)                        |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 3. Pipeline Orchestrator (pipeline.py)                                        |
|                                                                               |
|   Step A: Draft Generation (explainers/llm.py)                                |
|           LLM #1 drafts explanation with citations: [r1.net_revenue]          |
|                                                                               |
|   Step B: Strict Validation (validator.py)                                    |
|           Checks every number, citation tag, and percentage against facts     |
|                                                                               |
|   Step C: Retry if Failed (explainers/llm.py)                                 |
|           If issues found, LLM #2 receives error feedback to repair draft     |
|                                                                               |
|   Step D: Deterministic Fallback (explainers/template.py)                     |
|           If retry still fails, template explainer produces a verified draft  |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
| 4. Renderer (render.py or dashboard.py)                                       |
|    - Prints ASCII table + verified plain-text explanation                     |
+-------------------------------------------------------------------------------+
```

---

## 4. Database Schema & SQL Queries

The project contains a synthetic business database simulating an e-commerce company (`ecommerce.db`).

### Schema Tables (`sql/schema.sql`)
1. **`customers`** (2,500 rows): `customer_id`, `region`, `segment` (Consumer, Corporate, Small Business), `signup_date`.
2. **`products`** (40 rows): `product_id`, `name`, `category`, `unit_price_cents`.
3. **`orders`** (4,310 rows): `order_id`, `customer_id`, `order_date`, `channel`, `status`, `delivery_date`.
4. **`order_items`** (7,515 rows): `order_id`, `product_id`, `quantity`, `unit_price_cents`, `discount_pct`.
5. **`returns`** (437 rows): `return_id`, `order_id`, `product_id`, `return_date`, `quantity`, `reason`.

> **Key Design Choice**: Money is stored as integer cents in the database to eliminate floating-point rounding errors. Queries aggregate in cents and divide by `100.0` at the very end.

### How SQL Files Are Structured
Every SQL question in `sql/questions/` starts with metadata comments that tell the engine how to format and interpret each column:

```sql
-- id: q01
-- title: Monthly revenue and order count
-- question: How did net revenue and the number of delivered orders change month by month in 2025?
-- columns: month=label, delivered_orders=count, net_revenue=currency
-- focus: net_revenue

SELECT
    strftime('%Y-%m', o.order_date) AS month,
    COUNT(DISTINCT o.order_id) AS delivered_orders,
    ROUND(
        SUM(
            oi.quantity * oi.unit_price_cents * (100 - oi.discount_pct) / 10000.0
        ),
        2
    ) AS net_revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
WHERE o.status = 'delivered'
  AND o.order_date >= '2025-01-01'
  AND o.order_date < '2026-01-01'
GROUP BY strftime('%Y-%m', o.order_date)
ORDER BY month ASC;
```

#### Supported Column Types:
- `label`: Non-numeric text (e.g., month `2025-01`, customer segment, product name).
- `currency`: Monetary values formatted with dollar signs and suffixes (e.g., `$327k`).
- `count`: Whole integer counts (e.g., `350`).
- `percent`: Percentages (e.g., `12.5%`).
- `number`: Generic decimal or numeric values.

---

## 5. Detailed Component Walkthrough with Code Snippets

### A. Running Safe Read-Only Queries (`db.py` & `questions.py`)

To prevent accidental modification or SQL injection vulnerabilities, connections are strictly read-only:

```python
# src/result_explainer/db.py
import sqlite3

def connect_read_only(db_path: Path) -> sqlite3.Connection:
    """Open SQLite connection strictly read-only using URI mode."""
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn
```

In `questions.py`, the query is executed and wrapped into a clean `QueryResult`:

```python
# src/result_explainer/questions.py
@dataclass(frozen=True)
class QueryResult:
    question: Question
    columns: list[str]
    rows: list[dict[str, Any]]

def run_question(question: Question, conn: sqlite3.Connection) -> QueryResult:
    cursor = conn.cursor()
    cursor.execute(question.sql)
    rows = [dict(row) for row in cursor.fetchall()]
    return QueryResult(question=question, columns=columns, rows=rows)
```

---

### B. Building the Fact Table (`facts.py`)

A raw table is difficult for LLMs to cite without confusion. The project converts the table into a `FactTable`. Each value gets a reference coordinate like `r1.net_revenue`.

```python
# src/result_explainer/facts.py
@dataclass(frozen=True)
class Fact:
    ref: str                # e.g., "r1.net_revenue"
    row_idx: int            # 1-indexed row number
    column: str             # Column name
    kind: ColumnKind        # currency, count, percent, etc.
    raw_value: Any          # Raw value from SQLite
    display_value: str      # Formatted value (e.g., "$327k")
    numeric_value: float | None # Float for math checking

def build_facts(result: QueryResult) -> FactTable:
    facts: dict[str, Fact] = {}
    for row_idx, row in enumerate(result.rows, start=1):
        for col_name, kind in result.question.columns.items():
            ref = f"r{row_idx}.{col_name}"
            raw = row[col_name]
            disp = format_value(raw, kind)
            num = numeric_value(raw)
            facts[ref] = Fact(ref=ref, row_idx=row_idx, column=col_name,
                              kind=kind, raw_value=raw, display_value=disp,
                              numeric_value=num)
    return FactTable(question=result.question, result=result, facts=facts)
```

**Example Fact Table output given to the LLM:**
```
r1.month = 2025-01
r1.delivered_orders = 350
r1.net_revenue = $327k (exact: 327450.0)
r2.month = 2025-02
r2.delivered_orders = 312
r2.net_revenue = $298k (exact: 298120.0)
```

---

### C. The Grounding Validator (`validator.py`)

The validator is the core innovation of the project. It uses regex patterns to parse every number and citation in the LLM's response:

```python
# Regular expressions used in validator.py
NUMBER_PATTERN = re.compile(r"""
    (?<![A-Za-z0-9_])
    (?P<sign>[+-])?
    (?P<currency>[$€£])?
    (?P<value>\d+(?:,\d{3})*(?:\.\d+)?)
    (?P<suffix>[%kKmMbBtT])?
    (?![A-Za-z0-9_])
""", re.VERBOSE)

CITATION_PATTERN = re.compile(r"\[(?P<ref>r\d+\.[A-Za-z0-9_]+)\]")
CALCULATION_PATTERN = re.compile(
    r"\[(?P<calc>(?:r\d+\.[A-Za-z0-9_]+|\d+(?:\.\d+)?)\s*[-+/*]\s*(?:r\d+\.[A-Za-z0-9_]+|\d+(?:\.\d+)?))\]"
)
```

#### What the Validator Checks:
1. **`no_citations`**: Did the LLM write text with numbers but completely omit citations?
2. **`uncited_number`**: Is there a number mentioned that has no citation bracket directly after it?
3. **`unknown_reference`**: Did the LLM invent a reference like `[r99.sales]` that doesn't exist?
4. **`invented_number`**: Does the cited number differ from the actual database value by more than the allowed tolerance?
5. **`mismatched_label`**: Did the LLM cite a row label incorrectly?
6. **`unsupported_calculation`**: If the LLM performed math like `[r2.net_revenue - r1.net_revenue]`, does the calculation match the stated difference?

If all numbers match and all citations are valid, it returns `ValidationResult(valid=True, issues=[])`.

---

### D. The Pipeline Orchestrator (`pipeline.py`)

The pipeline manages the lifecycle: **Draft -> Validate -> Retry -> Fallback**.

```python
# src/result_explainer/pipeline.py
def explain_facts(
    facts: FactTable,
    explainers: Sequence[Explainer],
    validator: Validator,
    max_retries: int = 1,
) -> Explanation:
    # 1. If result table is empty, return empty template immediately
    if facts.is_empty:
        return Explanation(text="The query returned no rows.", status="empty", ...)

    # 2. First attempt with primary explainer
    explainer = explainers[0]
    draft = explainer.explain(facts)
    validation = validator.validate(draft, facts)

    if validation.valid:
        return Explanation(text=draft, status="grounded", validation=validation)

    # 3. Retry loop: pass validator feedback to the next explainer
    current_feedback = validation.issues
    for attempt in range(max_retries):
        retry_explainer = explainers[min(attempt + 1, len(explainers) - 1)]
        draft = retry_explainer.explain(facts, feedback=current_feedback)
        validation = validator.validate(draft, facts)
        if validation.valid:
            return Explanation(text=draft, status="grounded", validation=validation)
        current_feedback = validation.issues

    # 4. Ultimate Safety Net: Deterministic Template Explainer
    template = TemplateExplainer()
    fallback_text = template.explain(facts)
    fallback_val = validator.validate(fallback_text, facts)
    return Explanation(text=fallback_text, status="fallback", validation=fallback_val)
```

---

### E. LLM Integration via OpenRouter (`explainers/llm.py`)

The LLM explainer communicates with the OpenRouter API using standard OpenAI-compatible JSON payloads, streamed with `httpx`:

#### API Details
- **Base URL**: `https://openrouter.ai/api/v1/chat/completions`
- **Authentication**: `Bearer {LLM_API_KEY}`
- **Temperature**: `0.0` (zero randomness for maximum factual adherence)
- **Draft Model**: `google/gemini-2.0-flash-001` (fast, structured generation)
- **Retry Model**: `google/gemini-2.0-flash-001` or model designated for repair

#### Prompt Construction:
```python
# Excerpt from src/result_explainer/explainers/llm.py
SYSTEM_PROMPT = """You are a precise data analyst explaining SQL query results.
Rules:
1. Every numeric claim MUST cite its source fact using [r<row>.<col>], e.g., $327k [r1.net_revenue].
2. For calculations between facts, cite the calculation: [r2.net_revenue - r1.net_revenue].
3. Never state a number without an immediate citation bracket.
4. Keep the explanation concise (2-4 sentences). Focus on key trends and extremes.
"""

def _build_payload(self, facts: FactTable, feedback: Sequence[ValidationIssue] | None):
    user_prompt = f"Question: {facts.question.title}\n\nFacts:\n{facts.as_prompt_block()}\n"
    if feedback:
        user_prompt += "\nYour previous draft had validation errors. Fix them:\n"
        for issue in feedback:
            user_prompt += f"- {issue.message}\n"
            
    return {
        "model": self.settings.model,
        "temperature": 0.0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
    }
```

---

## 6. CLI Commands Reference

You can interact with the project directly via terminal:

| Command | What It Does |
|---|---|
| `python -m result_explainer init-db` | Generates synthetic CSV data and creates `ecommerce.db` |
| `python -m result_explainer list` | Lists all 10 available SQL analytical questions |
| `python -m result_explainer run q01` | Runs query `q01` and prints the ASCII result table |
| `python -m result_explainer explain q01` | Runs query, extracts facts, and prints a grounded explanation |
| `python -m result_explainer check` | Evaluates all 10 questions and prints a validation report |
| `python -m result_explainer dashboard` | Launches the Streamlit web dashboard |
| `pytest` | Runs all 140 automated tests offline |

---

## 7. Interactive Web Dashboard (`dashboard.py`)

Running `python -m result_explainer dashboard` launches an interactive Streamlit UI on `http://localhost:8501`.

The dashboard lets you:
1. **Select a Question**: Pick any of the 10 approved analytical questions.
2. **Inspect the SQL**: View the raw SQL query and column definitions.
3. **View Query Results**: Inspect the output table returned from SQLite.
4. **Choose Explainer Mode**:
   - `LLM Explainer`: Generates grounded explanations with live model generation.
   - `Template Explainer`: Generates deterministic rule-based explanations.
   - `Faulty Explainer`: A demo explainer that intentionally inflates numbers by 25% to demonstrate the validator catching errors.
5. **View Fact Table & Validation Details**: Inspect citations, tokens, and verified numeric bindings in real time.

---

## 8. Summary of Benefits

- **100% Verifiable**: Every single number has a coordinate linking back to SQLite.
- **Fail-Safe**: If an LLM hallucinates, it is corrected or replaced with a template.
- **Fast & Lightweight**: Zero heavy frameworks; built with pure Python, SQLite, and standard HTTP requests.
- **Read-Only Security**: Prevents SQL injection or data tampering by enforcing SQLite URI read-only locks.
