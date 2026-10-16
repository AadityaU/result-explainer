# Design and decision note: SQL Result Explainer

**Goal.** Explain the results of approved analytics queries in plain language, never inventing
a value and always pointing at the returned metric each claim comes from.

## Key decisions

1. **Approved SQL only, no text-to-SQL.** Generated SQL adds a second way to be wrong: a faulty
   query explained faithfully is still a wrong answer. Each question is one reviewed `.sql` file
   whose header declares its columns and types, and results that don't match are refused.
   *Trade-off:* no ad-hoc questions.

2. **SQL computes, the model narrates.** Growth, shares, averages and rates are query columns, so
   every number in the text must already exist in the result. *Trade-off:* a comparison the query
   didn't compute can't be stated. Add a column instead.

3. **Fact ids and per-sentence citations.** Every cell becomes `[r{row}.{column}]`. A number must
   match a fact cited *in the same sentence*, and any row the sentence names must be one it cites.
   This makes "always references returned metrics" a check rather than a prompt wish, and it
   catches real numbers attached to the wrong row.

4. **A deterministic validator, not an LLM judge.** Regex extraction plus `Decimal` matching is
   fast, explainable (each issue names the number and sentence) and testable offline. Faithful
   rounding (`$327.5k` for `$327,496.25`) passes. Truncation (`$327k`) doesn't.

5. **One retry, then a template fallback.** The validator's issues go back to the model with the
   retry. The deterministic template is tested to pass the validator on every question, so the
   user always gets a grounded answer, labelled `grounded`, `fallback`, `template` or `empty`.
   Empty results never reach a model, since with no rows it could only make something up.

6. **Models routed automatically, chosen by measurement.** Only `explainers/llm.py` calls a
   model (OpenRouter by default, any OpenAI-compatible endpoint, so Ollama works too), and
   `LLM_API_KEY` is the only setting. `google/gemini-4-argon` drafts. `z-ai/glm-5.3` only sees a
   draft that failed validation, with its issues, or takes over when Gemini errors or misses the
   45 s deadline. In evaluation both models were grounded on every answer, but Gemini never took
   more than 13.2 s while 5 of 27 GLM-5.3 answers took over 30 s (the slowest 435 s).
   Predictable speed was worth the ~$0.004 per answer GLM saves, so GLM is the cheap,
   independent second opinion. It replaced `glm-5.3-flash`, which was slower.

7. **SQLite and seeded synthetic data.** No install, read-only connections, money in integer
   cents. One seeded RNG with integer weights makes the committed CSVs reproducible byte for
   byte, and a test enforces it. The data has realistic shape: a holiday peak, November
   discounts, Apparel returns and a small, slow region.

## What evaluation against real models found

`evaluate` (see `docs/model-evaluation.md`) found two bugs the offline tests missed. Both
models cite several facts in one bracket, `[r1.net_revenue, r1.delivered_orders]`, which the
validator treated as uncited, so it rejected grounded answers. Accepting grouped citations fixed
this without loosening any check. And answers took up to 435 s despite a 120 s timeout, because
httpx only limits the gap between bytes and OpenRouter keeps slow requests alive. Every answer
now has a hard deadline. The few remaining rejections were the strict row rule working as
intended, and the retry fixed each one.

## Edge cases covered

NULL growth in the first month (`n/a`, can't back a number) · single-row result · ties in
rankings (stable by id) · a real zero (no returning customers in Q1) · empty result · numbers
attributed to the wrong row · invented multiples ("doubled") · slow, unreachable or
misconfigured model endpoint · unknown question ids · a missing database.

## Known limitations

The validator doesn't check direction words ("rose" vs "fell", since signs are compared as
absolute values), qualitative claims with no number or row name, or month names written instead
of `2025-03` labels. The prompt asks for these, but nothing enforces them.

## Next steps

Map month names to their labels · check direction words against the sign of the cited fact ·
parameterised questions with allow-listed values · re-run the evaluation regularly, since hosted
models change under the same name.
