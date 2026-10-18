# Model evaluation

How the models were chosen. Every number below comes from real runs of
`python -m result_explainer evaluate` against OpenRouter on 2026-10-17. A run sends all ten
approved questions through a setup. "Alone" gives one model both attempts. "Routed" is what users
get: the draft model answers, and the retry model only sees a rejected or failed draft. q10 is
empty by design and never reaches a model, so each run has nine model answers.

## Summary

After the grouped-citation fix (see below), across every run of each model:

| Model | Answers | Grounded | First attempt | Median time | Over 30 s | Slowest |
|-------|--------:|---------:|--------------:|------------:|----------:|--------:|
| `google/gemini-4-argon` | 36 | 36 | 35 | 6.9 s | 0 | 13.2 s |
| `z-ai/glm-5.3` | 27 | 27 | 26 | 6.3 s | 5 | 435.1 s |
| `z-ai/glm-5.3-flash` | 9 | 9 | 8 | 9.6 s | 1 | 178.1 s |
| **Routed: Gemini, then GLM-5.3** | 9 | 9 | 9 | 5.6 s | 0 | 9.9 s |

Prices on OpenRouter per million tokens (input / output): Gemini 4 Argon $2 / $10, GLM-5.3
$0.079 / $4.80, GLM-5.3 Flash $0.016 / $0.79. One answer uses roughly 1.5k input and 250 output
tokens, so Gemini costs about half a cent per answer and GLM-5.3 about a tenth of a cent.

## Decision

- **GLM-5.3 replaced GLM-5.3 Flash.** It was grounded on the first attempt more often and was
  faster, although both had multi-minute outliers.
- **Gemini 4 Argon drafts.** Gemini and GLM-5.3 are equally grounded, but Gemini never took
  longer than 13.2 s, while 5 of 27 GLM-5.3 answers took over 30 s and two took 349 s and 435 s.
  For an interactive tool, predictable speed is worth about $0.004 per answer.
- **GLM-5.3 retries.** It only runs when Gemini's answer fails validation, errors, or misses the
  45 s deadline. Being from a different model family, it gives an independent second attempt,
  and it covers a Gemini outage. The deadline also caps GLM's slow outliers.

## What the runs found

1. **Grouped citations were rejected.** In the first run both models often wrote
   `[r1.net_revenue, r1.delivered_orders]`. The validator only read one id per bracket, so it
   called those numbers uncited and rejected answers that were fully grounded. Before the fix,
   GLM-5.3 Flash was grounded 8/9 (6 on the first attempt) and Gemini 9/9 (8 on the first
   attempt). After it, they scored 9/9 (8) and 9/9 (9). No check was loosened.
2. **Timeouts didn't bound response time.** GLM-5.3 answers took 349 s and 435 s with a 120 s
   timeout, because httpx's timeout limits the gap between bytes and OpenRouter keeps slow
   requests alive. Each answer now has a hard deadline (45 s by default).
3. **The strict row rule fires rarely, and correctly.** The only remaining first-attempt
   rejections were answers naming a region they didn't cite ("East followed North…"). The
   retry fixed every one.

## Runs

| Run | Setups | Notes |
|-----|--------|-------|
| 1 | GLM-5.3 Flash, Gemini | Before the grouped-citation fix |
| 2 | GLM-5.3 Flash, GLM-5.3, Gemini | After the fix |
| 3 | GLM-5.3, Gemini | Exposed the unbounded response time; stopped before its routed setup |
| 4 | Gemini, GLM-5.3, routed | Final configuration, 45 s deadline; full report below |

## Final run (run 4)

| Setup | Result |
|-------|--------|
| google/gemini-4-argon alone | 9/9 grounded (8 on the first attempt), 0 fallback, 1 empty result(s) skipped |
| z-ai/glm-5.3 alone | 9/9 grounded (8 on the first attempt), 0 fallback, 1 empty result(s) skipped |
| routed: google/gemini-4-argon, then z-ai/glm-5.3 | 9/9 grounded (9 on the first attempt), 0 fallback, 1 empty result(s) skipped |

### google/gemini-4-argon alone

```text
id    status     attempts  seconds  answered by                       issues
q01   grounded          1      8.9  llm (google/gemini-4-argon)       -
q02   grounded          1      8.4  llm (google/gemini-4-argon)       -
q03   grounded          2     12.9  llm (google/gemini-4-argon)       mismatched_label
q04   grounded          1      5.3  llm (google/gemini-4-argon)       -
q05   grounded          1      7.8  llm (google/gemini-4-argon)       -
q06   grounded          1      4.7  llm (google/gemini-4-argon)       -
q07   grounded          1      5.4  llm (google/gemini-4-argon)       -
q08   grounded          1      5.0  llm (google/gemini-4-argon)       -
q09   grounded          1      5.2  llm (google/gemini-4-argon)       -
q10   empty             0      0.0  template                          -
```

#### q01: Monthly revenue and order count

**grounded** after 1 attempt(s), 8.9s

> In 2025-01, the year began with 263 [r1.delivered_orders] delivered orders and $87,181.29 [r1.net_revenue] in net revenue, before dropping to the lowest levels of the year in 2025-02 at 248 [r2.delivered_orders] orders and $80,656.39 [r2.net_revenue]. From 2025-03 through 2025-05, both metrics rose each month, going from 298 [r3.delivered_orders] orders and $87,591.23 [r3.net_revenue] to 299 [r4.delivered_orders] orders and $91,206.99 [r4.net_revenue] in 2025-04, and reaching 318 [r5.delivered_orders] orders and $93,652.16 [r5.net_revenue] in 2025-05. During the middle of the year, results fluctuated as 2025-06 had 309 [r6.delivered_orders] orders and $95,980.40 [r6.net_revenue], 2025-07 had 299 [r7.delivered_orders] orders and $95,479.82 [r7.net_revenue], and 2025-08 had 312 [r8.delivered_orders] orders and $93,604.98 [r8.net_revenue]. Starting in 2025-09, both figures increased every month from 328 [r9.delivered_orders] orders and $102,643.40 [r9.net_revenue] to 361 [r10.delivered_orders] orders and $120,346.63 [r10.net_revenue] in 2025-10, and 472 [r11.delivered_orders] orders and $142,242.48 [r11.net_revenue] in 2025-11. The year ended with its highest totals in 2025-12, recording 529 [r12.delivered_orders] delivered orders and $170,979.87 [r12.net_revenue] in net revenue.

#### q02: Top 10 products by net revenue

**grounded** after 1 attempt(s), 8.4s

> Among the top 10 [meta.row_count] products by net revenue, the USB-C Hub in the Electronics category [r1.category] ranked 1 [r1.rank] with $107,731.83 [r1.net_revenue] in revenue from 243 [r1.units_sold] units sold. Other top Electronics [r2.category] products included Wireless Earbuds at rank 2 [r2.rank] with $94,092.91 [r2.net_revenue] and 216 [r2.units_sold] units, followed by the Portable Charger at rank 3 [r3.rank] with $86,421.78 [r3.net_revenue] and 227 [r3.units_sold] units. The Outdoor category [r4.category] captured ranks 4 [r4.rank] through 7 [r7.rank], consisting of the Headlamp ($79,471.54 [r4.net_revenue], 277 [r4.units_sold] units), Trail Backpack ($68,335.12 [r5.net_revenue], 256 [r5.units_sold] units), Insulated Bottle ($63,949.14 [r6.net_revenue], 294 [r6.units_sold] units), and Rain Shell ($59,557.92 [r7.net_revenue], 237 [r7.units_sold] units). The list rounds out with three more Electronics [r8.category] items: the HD Webcam at rank 8 [r8.rank] ($56,926.91 [r8.net_revenue], 257 [r8.units_sold] units), Smart Plug at rank 9 [r9.rank] ($51,650.07 [r9.net_revenue], 251 [r9.units_sold] units), and Bluetooth Speaker at rank 10 [r10.rank] ($42,682.00 [r10.net_revenue], 248 [r10.units_sold] units). Note that while the question asks about 2025, the provided facts do not specify the year.

#### q03: Revenue and average order value by region

**grounded** after 2 attempt(s), 12.9s

> The North region recorded the largest net revenue at $327,496.25 [r1.net_revenue] across 1,008 [r1.delivered_orders] delivered orders, as well as the highest average order value of $324.90 [r1.avg_order_value]. The East region generated $297,743.54 [r2.net_revenue] in net revenue from 976 [r2.delivered_orders] delivered orders, with an average order value of $305.07 [r2.avg_order_value]. The South and West regions had lower net revenues of $276,968.74 [r3.net_revenue] and $258,513.97 [r4.net_revenue] from 883 [r3.delivered_orders] and 820 [r4.delivered_orders] delivered orders, respectively, while posting average order values of $313.67 [r3.avg_order_value] and $315.26 [r4.avg_order_value]. Finally, the Central region had the smallest figures across all metrics, with $100,843.14 [r5.net_revenue] in net revenue, 349 [r5.delivered_orders] delivered orders, and an average order value of $288.95 [r5.avg_order_value].

Rejected attempt 1 (llm (google/gemini-4-argon)): Across the 5 [meta.row_count] customer regions, the North region generated the largest net revenue at $327,496.25 [r1.net_revenue] and the highest average order value at $324.90 [r1.avg_order_value] across 1,008 [r1.delivered_orders] delivered orders. The East region followed in net revenue with $297,743.54 [r2.net_revenue] from 976 [r2.delivered_orders] delivered orders, though its average order value was lower at $305.07 [r2.avg_order_value]. The South and West regions had lower net revenues of $276,968.74 [r3.net_revenue] and $258,513.97 [r4.net_revenue] from 883 [r3.delivered_orders] and 820 [r4.delivered_orders] delivered orders, respectively, while posting higher average order values than the East at $313.67 [r3.avg_order_value] and $315.26 [r4.avg_order_value]. Finally, the Central region recorded the smallest results across all metrics, with 349 [r5.delivered_orders] delivered orders, $100,843.14 [r5.net_revenue] in net revenue, and an average order value of $288.95 [r5.avg_order_value].

- `mismatched_label`: "East" is named, but none of the facts cited in this sentence are for it

#### q04: Revenue share by sales channel

**grounded** after 1 attempt(s), 5.3s

> Net revenue is distributed across 3 [meta.row_count] sales channels. The web [r1.channel] channel generated the largest share at 54.4% [r1.revenue_share_pct], bringing in $686,268.22 [r1.net_revenue] from 2,197 [r1.delivered_orders] delivered orders. The mobile [r2.channel] channel accounted for a 30.9% [r2.revenue_share_pct] share, totaling $389,893.09 [r2.net_revenue] across 1,259 [r2.delivered_orders] delivered orders. The marketplace [r3.channel] channel had the smallest share at 14.7% [r3.revenue_share_pct], with $185,404.33 [r3.net_revenue] in net revenue from 580 [r3.delivered_orders] delivered orders.

#### q05: Month-over-month revenue growth

**grounded** after 1 attempt(s), 7.8s

> In 2025-01 [r1.month], net revenue was $87,181.29 [r1.net_revenue], while the previous month's revenue and growth percentage are not available [r1.previous_month_revenue, r1.growth_pct]. Net revenue shrank by -7.5% [r2.growth_pct] to $80,656.39 [r2.net_revenue] in 2025-02 [r2.month], before growing by 8.6% [r3.growth_pct] in 2025-03 [r3.month], 4.1% [r4.growth_pct] in 2025-04 [r4.month], 2.7% [r5.growth_pct] in 2025-05 [r5.month], and 2.5% [r6.growth_pct] in 2025-06 [r6.month]. Revenue then shrank by -0.5% [r7.growth_pct] in 2025-07 [r7.month] and -2.0% [r8.growth_pct] in 2025-08 [r8.month]. Growth resumed in 2025-09 [r9.month] at 9.7% [r9.growth_pct], followed by 17.2% [r10.growth_pct] in 2025-10 [r10.month] and 18.2% [r11.growth_pct] in 2025-11 [r11.month]. Finally, 2025-12 [r12.month] saw the largest growth at 20.2% [r12.growth_pct], reaching a net revenue of $170,979.87 [r12.net_revenue].

#### q06: Repeat-customer rate

**grounded** after 1 attempt(s), 4.7s

> There were 1,722 [r1.customers_with_orders] customers with orders in the results. Out of that group, 956 [r1.repeat_customers] were repeat customers who came back for at least one more order. This represents a repeat-customer rate of 55.5% [r1.repeat_rate_pct]. Please note that the provided facts do not explicitly state whether these figures are strictly for the year 2025.

#### q07: Return rate by category

**grounded** after 1 attempt(s), 5.4s

> Across the 5 [meta.row_count] product categories, Apparel has the largest share of units returned at 11.6% [r1.return_rate_pct], with 233 [r1.units_returned] units returned out of 2,007 [r1.units_sold] units sold. Outdoor has the next highest return rate at 5.6% [r2.return_rate_pct], based on 108 [r2.units_returned] returned units from 1,945 [r2.units_sold] units sold. Electronics and Home show lower return rates of 4.3% [r3.return_rate_pct] and 2.9% [r4.return_rate_pct], with 84 [r3.units_returned] and 56 [r4.units_returned] units returned, respectively. Books has the smallest return rate at 1.9% [r5.return_rate_pct], with 36 [r5.units_returned] units returned out of 1,889 [r5.units_sold] units sold.

#### q08: New vs returning customers by quarter

**grounded** after 1 attempt(s), 5.0s

> In 2025-Q1 [r1.quarter], there were 613 [r1.active_customers] active customers, consisting of 613 [r1.new_customers] new customers and 0 [r1.returning_customers] returning customers. In 2025-Q2 [r2.quarter], the 669 [r2.active_customers] active customers included 412 [r2.new_customers] new customers and 257 [r2.returning_customers] returning customers. By 2025-Q3 [r3.quarter], returning customers were higher than new ones, with 376 [r3.returning_customers] returning and 310 [r3.new_customers] new out of 686 [r3.active_customers] active customers. Finally, 2025-Q4 [r4.quarter] had the largest total with 942 [r4.active_customers] active customers, made up of 387 [r4.new_customers] new customers and 555 [r4.returning_customers] returning customers.

#### q09: Delivery time by region

**grounded** after 1 attempt(s), 5.2s

> The Central region has the highest average delivery time at 7.4 [r1.avg_delivery_days] days across 349 [r1.delivered_orders] delivered orders, with its slowest delivery taking 11 [r1.max_delivery_days] days. In the West region, delivery takes an average of 6.1 [r2.avg_delivery_days] days with a maximum of 9 [r2.max_delivery_days] days across 820 [r2.delivered_orders] orders. The South region averages 5.6 [r3.avg_delivery_days] days with a slowest time of 8 [r3.max_delivery_days] days across 883 [r3.delivered_orders] orders, while the North region averages 4.5 [r4.avg_delivery_days] days with a maximum of 7 [r4.max_delivery_days] days across 1,008 [r4.delivered_orders] orders. Finally, the East region has the lowest delivery times across its 976 [r5.delivered_orders] orders, averaging 4.0 [r5.avg_delivery_days] days with a slowest delivery of 6 [r5.max_delivery_days] days.

#### q10: Orders that missed the 14-day delivery promise

**empty** after 0 attempt(s), 0.0s

> The query returned 0 rows [meta.row_count], so nothing matched the question "Orders that missed the 14-day delivery promise".

### z-ai/glm-5.3 alone

```text
id    status     attempts  seconds  answered by                       issues
q01   grounded          1     11.4  llm (z-ai/glm-5.3)                -
q02   grounded          1     18.0  llm (z-ai/glm-5.3)                -
q03   grounded          2     38.2  llm (z-ai/glm-5.3)                mismatched_label
q04   grounded          1      7.8  llm (z-ai/glm-5.3)                -
q05   grounded          1      2.4  llm (z-ai/glm-5.3)                -
q06   grounded          1      2.5  llm (z-ai/glm-5.3)                -
q07   grounded          1      4.0  llm (z-ai/glm-5.3)                -
q08   grounded          1     11.1  llm (z-ai/glm-5.3)                -
q09   grounded          1      5.2  llm (z-ai/glm-5.3)                -
q10   empty             0      0.0  template                          -
```

#### q01: Monthly revenue and order count

**grounded** after 1 attempt(s), 11.4s

> Net revenue and delivered orders both grew over the year, starting at $87,181.29 and 263 delivered orders in January [r1.net_revenue][r1.delivered_orders]. February dipped to $80,656.39 in net revenue with 248 delivered orders [r2.net_revenue][r2.delivered_orders], after which both measures generally climbed through the middle of the year, with June reaching $95,980.40 and 309 delivered orders [r6.net_revenue][r6.delivered_orders]. The strongest months came at the end of the year: November delivered 472 orders and $142,242.48 in net revenue [r11.delivered_orders][r11.net_revenue], and December was the highest of the year with 529 delivered orders and $170,979.87 in net revenue [r12.delivered_orders][r12.net_revenue]. Overall, the monthly figures show a clear upward trend in both revenue and order volume across 2025.

#### q02: Top 10 products by net revenue

**grounded** after 1 attempt(s), 18.0s

> The top product by net revenue was the USB-C Hub in Electronics, which earned $107,731.83 [r1.net_revenue] on 243 units sold [r1.units_sold]. It was followed by Wireless Earbuds, which brought in $94,092.91 [r2.net_revenue] from 216 units [r2.units_sold], and Portable Charger with $86,421.78 [r3.net_revenue] from 227 units [r3.units_sold]. Outdoor products held the next four spots: the Headlamp earned $79,471.54 [r4.net_revenue] on 277 units [r4.units_sold], the Trail Backpack $68,335.12 [r5.net_revenue] on 256 units [r5.units_sold], the Insulated Bottle $63,949.14 [r6.net_revenue] on 294 units [r6.units_sold], and the Rain Shell $59,557.92 [r7.net_revenue] on 237 units [r7.units_sold]. The list rounded out with the HD Webcam at $56,926.91 [r8.net_revenue] and 257 units [r8.units_sold], the Smart Plug at $51,650.07 [r9.net_revenue] and 251 units [r9.units_sold], and the Bluetooth Speaker at $42,682.00 [r10.net_revenue] and 248 units [r10.units_sold].

#### q03: Revenue and average order value by region

**grounded** after 2 attempt(s), 38.2s

> North has the largest net revenue at $327,496.25 [r1.net_revenue] and the largest average order value at $324.90 [r1.avg_order_value]. East has net revenue of $297,743.54 [r2.net_revenue] with an average order value of $305.07 [r2.avg_order_value]. South's net revenue is $276,968.74 [r3.net_revenue] and its average order value is $313.67 [r3.avg_order_value], while West has net revenue of $258,513.97 [r4.net_revenue] with an average order value of $315.26 [r4.avg_order_value]. Central is the smallest region on both measures, with net revenue of $100,843.14 [r5.net_revenue] and an average order value of $288.95 [r5.avg_order_value]. Across all regions, average order value ranges from $288.95 [r5.avg_order_value] in Central to $324.90 [r1.avg_order_value] in North.

Rejected attempt 1 (llm (z-ai/glm-5.3)): North leads all regions with net revenue of $327,496.25 [r1.net_revenue] and the highest average order value at $324.90 [r1.avg_order_value]. Central is the smallest on both measures, with net revenue of $100,843.14 [r5.net_revenue] and an average order value of $288.95 [r5.avg_order_value]. East brings in more net revenue than South, at $297,743.54 [r2.net_revenue] versus $276,968.74 [r3.net_revenue], yet its average order value of $305.07 [r2.avg_order_value] is lower than South's $313.67 [r3.avg_order_value]. West shows a similar pattern, with a higher average order value of $315.26 [r4.avg_order_value] than East, even though its net revenue of $258,513.97 [r4.net_revenue] is lower.

- `mismatched_label`: "East" is named, but none of the facts cited in this sentence are for it

#### q04: Revenue share by sales channel

**grounded** after 1 attempt(s), 7.8s

> Web was the largest sales channel, accounting for 54.4% of net revenue, or $686,268.22 [r1.revenue_share_pct][r1.net_revenue]. Mobile contributed 30.9% of net revenue, which came to $389,893.09 [r2.revenue_share_pct][r2.net_revenue]. Marketplace was the smallest channel, bringing in $185,404.33, or 14.7% of net revenue [r3.net_revenue][r3.revenue_share_pct]. Web also had the most delivered orders at 2,197, compared with 1,259 for mobile and 580 for marketplace [r1.delivered_orders][r2.delivered_orders][r3.delivered_orders].

#### q05: Month-over-month revenue growth

**grounded** after 1 attempt(s), 2.4s

> Net revenue grew in most months of 2025, with the strongest gains coming at the end of the year: October grew 17.2% [r10.growth_pct], November grew 18.2% [r11.growth_pct], and December grew 20.2% [r12.growth_pct], reaching $170,979.87 [r12.net_revenue]. The only declines were in February, down 7.5% to $80,656.39 [r2.growth_pct] [r2.net_revenue], and in July and August, which fell 0.5% and 2.0% respectively [r7.growth_pct] [r8.growth_pct]. The largest single-month jump was September's 9.7% increase to $102,643.40 [r9.growth_pct] [r9.net_revenue]. Growth for January is not available because there is no prior month to compare it to [r1.growth_pct].

#### q06: Repeat-customer rate

**grounded** after 1 attempt(s), 2.5s

> In 2025, 1,722 customers received at least one order [r1.customers_with_orders]. Of those, 956 customers came back for at least one more order [r1.repeat_customers]. That works out to a repeat-customer rate of 55.5% [r1.repeat_rate_pct]. In other words, a majority of the customers who received an order in 2025 went on to order again.

#### q07: Return rate by category

**grounded** after 1 attempt(s), 4.0s

> Apparel has the highest return rate at 11.6% [r1.return_rate_pct], with 233 units returned out of 2,007 sold [r1.units_returned] [r1.units_sold]. Outdoor is next at 5.6% [r2.return_rate_pct], followed by Electronics at 4.3% [r3.return_rate_pct]. Home has a lower return rate of 2.9% [r4.return_rate_pct]. Books has the smallest return rate at 1.9% [r5.return_rate_pct].

#### q08: New vs returning customers by quarter

**grounded** after 1 attempt(s), 11.1s

> In 2025-Q1 [r1.quarter], all 613 active customers were new [r1.new_customers], with 0 returning [r1.returning_customers]. In 2025-Q2 [r2.quarter], there were 669 active customers [r2.active_customers], made up of 412 new [r2.new_customers] and 257 returning [r2.returning_customers]. In 2025-Q3 [r3.quarter], active customers reached 686 [r3.active_customers], with 310 new [r3.new_customers] and 376 returning [r3.returning_customers]. 2025-Q4 [r4.quarter] had the largest number of active customers at 942 [r4.active_customers], consisting of 387 new [r4.new_customers] and 555 returning [r4.returning_customers]. New customers were largest in 2025-Q1 [r1.new_customers], while returning customers were largest in 2025-Q4 [r4.returning_customers].

#### q09: Delivery time by region

**grounded** after 1 attempt(s), 5.2s

> Average delivery time varies by region, with Central being the slowest at 7.4 days on average [r1.avg_delivery_days]. West follows at 6.1 days [r2.avg_delivery_days], then South at 5.6 days [r3.avg_delivery_days]. North averages 4.5 days [r4.avg_delivery_days], while East is the fastest at 4.0 days [r5.avg_delivery_days]. The slowest single delivery was in Central, taking 11 days [r1.max_delivery_days].

#### q10: Orders that missed the 14-day delivery promise

**empty** after 0 attempt(s), 0.0s

> The query returned 0 rows [meta.row_count], so nothing matched the question "Orders that missed the 14-day delivery promise".

### routed: google/gemini-4-argon, then z-ai/glm-5.3

```text
id    status     attempts  seconds  answered by                       issues
q01   grounded          1      9.9  llm (google/gemini-4-argon)       -
q02   grounded          1      8.9  llm (google/gemini-4-argon)       -
q03   grounded          1      6.8  llm (google/gemini-4-argon)       -
q04   grounded          1      4.9  llm (google/gemini-4-argon)       -
q05   grounded          1      8.8  llm (google/gemini-4-argon)       -
q06   grounded          1      2.8  llm (google/gemini-4-argon)       -
q07   grounded          1      5.6  llm (google/gemini-4-argon)       -
q08   grounded          1      5.4  llm (google/gemini-4-argon)       -
q09   grounded          1      5.6  llm (google/gemini-4-argon)       -
q10   empty             0      0.0  template                          -
```

#### q01: Monthly revenue and order count

**grounded** after 1 attempt(s), 9.9s

> In 2025, monthly performance started in 2025-01 [r1.month] with 263 [r1.delivered_orders] delivered orders and $87,181.29 [r1.net_revenue] in net revenue, before dipping to the lowest levels of the year in 2025-02 [r2.month] at 248 [r2.delivered_orders] orders and $80,656.39 [r2.net_revenue]. Both metrics generally increased through the spring, reaching 298 [r3.delivered_orders] orders and $87,591.23 [r3.net_revenue] in 2025-03 [r3.month], 299 [r4.delivered_orders] orders and $91,206.99 [r4.net_revenue] in 2025-04 [r4.month], and 318 [r5.delivered_orders] orders with $93,652.16 [r5.net_revenue] in 2025-05 [r5.month]. During the summer, results fluctuated slightly with 309 [r6.delivered_orders] orders and $95,980.40 [r6.net_revenue] in 2025-06 [r6.month], 299 [r7.delivered_orders] orders and $95,479.82 [r7.net_revenue] in 2025-07 [r7.month], and 312 [r8.delivered_orders] orders and $93,604.98 [r8.net_revenue] in 2025-08 [r8.month]. Growth picked up consistently in the final four months, rising from 328 [r9.delivered_orders] orders and $102,643.40 [r9.net_revenue] in 2025-09 [r9.month] to 361 [r10.delivered_orders] orders and $120,346.63 [r10.net_revenue] in 2025-10 [r10.month]. The year ended with the highest figures in the final two months, recording 472 [r11.delivered_orders] orders and $142,242.48 [r11.net_revenue] in 2025-11 [r11.month], and peaking at 529 [r12.delivered_orders] delivered orders and $170,979.87 [r12.net_revenue] in 2025-12 [r12.month].

#### q02: Top 10 products by net revenue

**grounded** after 1 attempt(s), 8.9s

> Among the top 10 [meta.row_count] products by net revenue, the USB-C Hub in the Electronics category [r1.category] ranked 1 [r1.rank] with $107,731.83 [r1.net_revenue] from 243 [r1.units_sold] units sold. Other top Electronics products included Wireless Earbuds at rank 2 [r2.rank] with $94,092.91 [r2.net_revenue] and 216 [r2.units_sold] units sold, and the Portable Charger at rank 3 [r3.rank] with $86,421.78 [r3.net_revenue] and 227 [r3.units_sold] units sold. Products in the Outdoor category [r4.category] held ranks 4 [r4.rank] through 7 [r7.rank]: the Headlamp generated $79,471.54 [r4.net_revenue] across 277 [r4.units_sold] units, the Trail Backpack earned $68,335.12 [r5.net_revenue] with 256 [r5.units_sold] units, the Insulated Bottle reached $63,949.14 [r6.net_revenue] with 294 [r6.units_sold] units, and the Rain Shell brought in $59,557.92 [r7.net_revenue] from 237 [r7.units_sold] units. Rounding out the list in the Electronics category [r8.category] were the HD Webcam at rank 8 [r8.rank] ($56,926.91 [r8.net_revenue] and 257 [r8.units_sold] units), the Smart Plug at rank 9 [r9.rank] ($51,650.07 [r9.net_revenue] and 251 [r9.units_sold] units), and the Bluetooth Speaker at rank 10 [r10.rank] ($42,682.00 [r10.net_revenue] and 248 [r10.units_sold] units). Note that while the question asks about 2025, the provided facts do not specify the year for these results.

#### q03: Revenue and average order value by region

**grounded** after 1 attempt(s), 6.8s

> Across the 5 [meta.row_count] customer regions, the North [r1.region] leads with the largest net revenue at $327,496.25 [r1.net_revenue] and the highest average order value at $324.90 [r1.avg_order_value] from 1,008 [r1.delivered_orders] delivered orders. The East [r2.region] generated $297,743.54 [r2.net_revenue] across 976 [r2.delivered_orders] orders with an average order value of $305.07 [r2.avg_order_value], while the South [r3.region] recorded $276,968.74 [r3.net_revenue] across 883 [r3.delivered_orders] orders with an average order value of $313.67 [r3.avg_order_value]. The West [r4.region] brought in a lower net revenue of $258,513.97 [r4.net_revenue] from 820 [r4.delivered_orders] delivered orders, though its average order value was $315.26 [r4.avg_order_value]. Finally, the Central [r5.region] region had the smallest net revenue at $100,843.14 [r5.net_revenue] and the lowest average order value at $288.95 [r5.avg_order_value] from 349 [r5.delivered_orders] delivered orders.

#### q04: Revenue share by sales channel

**grounded** after 1 attempt(s), 4.9s

> Net revenue is divided across 3 [meta.row_count] sales channels. The web channel [r1.channel] accounted for the largest share at 54.4% [r1.revenue_share_pct], generating $686,268.22 [r1.net_revenue] from 2,197 [r1.delivered_orders] delivered orders. The mobile channel [r2.channel] contributed 30.9% [r2.revenue_share_pct] of the revenue, with $389,893.09 [r2.net_revenue] across 1,259 [r2.delivered_orders] delivered orders. The marketplace channel [r3.channel] had the smallest share at 14.7% [r3.revenue_share_pct], bringing in $185,404.33 [r3.net_revenue] from 580 [r3.delivered_orders] delivered orders.

#### q05: Month-over-month revenue growth

**grounded** after 1 attempt(s), 8.8s

> In 2025-01, net revenue was $87,181.29 [r1.net_revenue], while previous month revenue [r1.previous_month_revenue] and growth percentage [r1.growth_pct] are not available. Net revenue shrank by -7.5% [r2.growth_pct] to $80,656.39 [r2.net_revenue] in 2025-02, before growing by 8.6% [r3.growth_pct] in 2025-03, 4.1% [r4.growth_pct] in 2025-04, 2.7% [r5.growth_pct] in 2025-05, and 2.5% [r6.growth_pct] to reach $95,980.40 [r6.net_revenue] in 2025-06. Revenue then decreased by -0.5% [r7.growth_pct] in 2025-07 and -2.0% [r8.growth_pct] in 2025-08, dropping to $93,604.98 [r8.net_revenue]. Finally, month-over-month revenue grew consecutively through the end of the year by 9.7% [r9.growth_pct] in 2025-09, 17.2% [r10.growth_pct] in 2025-10, 18.2% [r11.growth_pct] in 2025-11, and 20.2% [r12.growth_pct] in 2025-12 to finish at $170,979.87 [r12.net_revenue].

#### q06: Repeat-customer rate

**grounded** after 1 attempt(s), 2.8s

> A total of 1,722 [r1.customers_with_orders] customers received an order. Out of those customers, 956 [r1.repeat_customers] returned to serve as repeat customers. This results in a repeat-customer rate of 55.5% [r1.repeat_rate_pct]. While the question asks specifically about the year 2025, the provided facts do not specify the time period for these figures.

#### q07: Return rate by category

**grounded** after 1 attempt(s), 5.6s

> Among the 5 [meta.row_count] product categories, Apparel has the largest share of returns at 11.6% [r1.return_rate_pct], with 233 [r1.units_returned] units returned out of 2,007 [r1.units_sold] units sold. Outdoor has the next highest return rate at 5.6% [r2.return_rate_pct] from 108 [r2.units_returned] returned units and 1,945 [r2.units_sold] sold, followed by Electronics at 4.3% [r3.return_rate_pct] with 84 [r3.units_returned] returns out of 1,939 [r3.units_sold] units sold. Home has a lower return rate of 2.9% [r4.return_rate_pct], recording 56 [r4.units_returned] units returned from 1,905 [r4.units_sold] sold. Books has the smallest return rate at 1.9% [r5.return_rate_pct], with 36 [r5.units_returned] units returned out of 1,889 [r5.units_sold] units sold.

#### q08: New vs returning customers by quarter

**grounded** after 1 attempt(s), 5.4s

> In 2025-Q1 [r1.quarter], there were 613 [r1.active_customers] active customers, consisting of 613 [r1.new_customers] new customers and 0 [r1.returning_customers] returning customers. In 2025-Q2 [r2.quarter], the 669 [r2.active_customers] active customers included 412 [r2.new_customers] new customers and 257 [r2.returning_customers] returning customers. By 2025-Q3 [r3.quarter], returning customers were higher than new customers, with 376 [r3.returning_customers] returning and 310 [r3.new_customers] new out of 686 [r3.active_customers] total active customers. Finally, 2025-Q4 [r4.quarter] had the largest active customer base at 942 [r4.active_customers], made up of 387 [r4.new_customers] new customers and 555 [r4.returning_customers] returning customers.

#### q09: Delivery time by region

**grounded** after 1 attempt(s), 5.6s

> Across the 5 [meta.row_count] regions, the Central region [r1.region] had the highest average delivery time at 7.4 [r1.avg_delivery_days] days and the slowest maximum delivery at 11 [r1.max_delivery_days] days across 349 [r1.delivered_orders] delivered orders. In the West region [r2.region], 820 [r2.delivered_orders] delivered orders averaged 6.1 [r2.avg_delivery_days] days with a maximum of 9 [r2.max_delivery_days] days, while the South region [r3.region] saw 883 [r3.delivered_orders] orders take an average of 5.6 [r3.avg_delivery_days] days and a maximum of 8 [r3.max_delivery_days] days. The North region [r4.region] recorded 1,008 [r4.delivered_orders] delivered orders with an average delivery of 4.5 [r4.avg_delivery_days] days and a slowest time of 7 [r4.max_delivery_days] days. Finally, the East region [r5.region] had the lowest average delivery time at 4.0 [r5.avg_delivery_days] days and a maximum of 6 [r5.max_delivery_days] days across 976 [r5.delivered_orders] orders.

#### q10: Orders that missed the 14-day delivery promise

**empty** after 0 attempt(s), 0.0s

> The query returned 0 rows [meta.row_count], so nothing matched the question "Orders that missed the 14-day delivery promise".
