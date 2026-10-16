# Design and decision note: SQL Result Explainer

**Goal.** Explain the results of approved analytics queries in plain language, never inventing
a value and always pointing at the returned metric each claim comes from.

## Key decisions

1. **Approved SQL only, no text-to-SQL.** The brief asks for curated questions, and generated SQL
   adds a second way to be wrong: a faulty query explained faithfully is still a wrong answer.
   Each question is one reviewed `.sql` file whose header declares its columns and their types,
   and the runner refuses results that don't match. *Trade-off:* no ad-hoc questions. A new
   question means a new reviewed file.

2. **SQL computes, the model narrates.** Growth, shares, averages and rates are columns in the
   query, so the validator can demand that every number in the text already exists in the
   result. *Trade-off:* the model can't offer a comparison the query didn't compute. Add a column
   rather than trusting arithmetic in prose.

3. **Fact ids and per-sentence citations.** Every cell becomes `[r{row}.{column}]`. A number must
   match a fact cited *in the same sentence*, and any row the sentence names must be one it
   cites. This turns "always references returned metrics" from a prompt wish into a check, and
   it catches real numbers attached to the wrong row.

4. **A deterministic validator, not an LLM judge.** Regex extraction plus `Decimal` matching is
   fast, explainable (each issue names the number and sentence), and fully testable offline. A
   faithful rounding (`$327.5k` for `$327,496.25`) is accepted, truncation (`$327k`) isn't, and
   rounding is half-up everywhere.

5. **One retry, then a template fallback.** Sending the issues back fixes most citation and
   formatting slips. A model that invents twice isn't trusted a third time. The deterministic
   template is tested to pass the validator on every question, so the user always gets a
   grounded answer, labelled as `grounded`, `fallback`, `template` or `empty`.

6. **Empty results never reach the model.** With no rows there is nothing to explain, and a
   model asked anyway can only make something up. q10 is empty by design to demonstrate this.

7. **One AI interface, OpenAI-compatible HTTP.** `Explainer.explain(facts, feedback)` is the only
   boundary, and only `explainers/llm.py` makes network calls. The same client works with local
   models (Ollama, LM Studio) and free hosted ones (Groq, OpenRouter), switched in `.env`. Keys
   live only in the environment, and tests mock the HTTP layer.

8. **SQLite and seeded synthetic data.** Zero install, a read-only connection mode, and money in
   integer cents. The generator uses one seeded RNG with integer weights, so the committed CSVs
   are reproducible byte for byte, and a test enforces it. The data has realistic shape: holiday
   peak, November discounts, Apparel returns, a small slow region.

## Edge cases covered

NULL growth in the first month (`n/a`, can't back a number) · single-row result · ties in
rankings (stable by id) · a real zero (no returning customers in Q1) · empty result · numbers
attributed to the wrong row · invented multiples ("doubled") · unreachable or misconfigured
endpoint · unknown question ids · a missing database.

## Known limitations

The validator doesn't check direction words ("rose" vs "fell", since signs are compared as
absolute values), qualitative claims with no number or row name, or month names written instead
of `2025-03` labels. The prompt asks for these, but nothing enforces them.

## Next steps

Map month names to their labels · check direction words against the sign of the cited fact ·
parameterised questions with allow-listed values · a small evaluation set that reports the
grounded-on-first-attempt rate per model.
