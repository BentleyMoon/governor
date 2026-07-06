# Governor: Workload-Classifying Proxy for LLM APIs

**Bentley Moon**
April 2026

> This is a public-facing extract of §5 ("Finding 3: Governor Routing") from a longer research synthesis on boundary mechanisms in AI systems. The full synthesis covers two additional findings — the multi-file wall in LLM code repair, and momentum protection in continual learning under metabolic energy constraint — alongside fourteen documented neural-module negative results.

## Abstract

Governor is a 3-tier classifier and proxy that routes LLM API requests to the cheapest tier whose quality is adequate for the workload. Across 35 measured turns spanning coding, debugging, research, and customer-support sessions, Governor produced 23–65% cost reduction with 95–96% quality retention on coding workloads, validated against simulated cloud pricing on published model rate cards.

The classifier itself is approximately 200 lines of keyword regex with no learned components, no embeddings, and no internal state model. The argument for keywords over a learned classifier is empirical: the decision-relevant signal for tier selection appears to be observable at the request boundary — in the words of the prompt — and a more sophisticated classifier did not improve the routing decision in our testing.

## 1. The Mechanism

Each turn of a conversation is classified into one of three tiers:

```
ECONOMY    →  greetings, acks, simple lookups, follow-ups   → cheap fast model
STANDARD   →  bounded coding, implementation, reasoning      → capable model
FRONTIER   →  architecture, multi-file refactor, security    → strongest model
```

Classification logic, in order of precedence:

1. Short input (≤10 words) containing a SIMPLE_TERM → **ECONOMY**
2. Input containing any FRONTIER_TERM → **FRONTIER**
3. Long input (>200 words) containing any CODING_TERM → **FRONTIER**
4. Input containing any CODING_TERM → **STANDARD**
5. CORRECTION_TERM or FRESHNESS_TERM with prior coding context in session → **STANDARD**
6. CORRECTION_TERM or FRESHNESS_TERM otherwise → **ECONOMY**
7. CLARIFICATION_TERM → **ECONOMY**
8. Default → **ECONOMY**

The full keyword lists are in `governor/router.py`. They are intended as a starting point and are tuned per deployment.

## 2. Measured Performance

| Scenario | Flat (frontier model) | Routed | Savings | Quality |
|----------|---:|---:|---:|---:|
| Mixed coding session | $0.194 | $0.100 | **49%** | 95% |
| Debugging session | $0.156 | $0.055 | **65%** | 96% |
| Research assistant | $0.052 | $0.004 | **92%*** | 100% |
| Customer support | $0.040 | $0.003 | **93%*** | 100% |

*Savings on research/support are high because most turns are simple lookups routed to ECONOMY. These figures are simulated-cost-dependent and should be read alongside the routing fraction.

Quality scoring: hand-rated on a 0–1 scale, blind to which tier produced the response, on the same scripted sessions used for cost measurement.

## 3. Containment

A separate containment validator built into the same proxy catches dangerous LLM proposals — workspace mutations and policy edits the system shouldn't admit. On 200 trials across 4 attack types (test-file mutation, delete-without-fallback, germline-without-dissent, policy-self-mutation):

- Adversarial detection rate: **100%** (55/55)
- False positive rate on valid proposals: **0%** (0/145)

This is reported alongside Governor because it shares the same architectural principle (boundary observation) and is implemented as a sibling module in the proxy.

## 4. Why a Regex Is Enough (the boring argument)

The hypothesis from the broader research program is that **boundary mechanisms outperform internal models when the sufficient statistic for the decision is observable at the system-environment interface.**

For tier selection, the sufficient statistic is the presence of coding/architecture keywords in the prompt — observable at the request boundary. A learned classifier could in principle do better, but in our testing keyword presence captured the routing-relevant signal cleanly enough that adding learned components didn't move the needle.

This is not a strong claim. It's an empirical observation that, given the labeled data we had, a regex was as good as anything else we tried. The hypothesis predicts failure modes:

- Workloads where complexity depends on context not present in the current turn (long-running negotiations, multi-document reasoning where the keywords are in the documents, not the prompt)
- Workloads where the relevant tier depends on the *response* the LLM will produce, not the request (creative work, planning)
- Non-English workloads (the keyword list is English-coding-centric)

These are all extension targets, not refutations. The regex-is-enough claim is bounded to the workloads tested.

## 5. Limitations

1. **Sample size.** Quality measurement is on 35 hand-rated turns. The 23–65% savings range is real but should be re-validated on each deployment's actual workload.

2. **Simulated costs.** Pricing is computed from published cloud rate cards. Customers with negotiated direct rates from OpenAI/Anthropic will see smaller savings.

3. **English-coding-centric.** The keyword list reflects the workloads tested. Non-English deployments will need keyword extension.

4. **Quality measurement is human-rated.** Different raters will produce different absolute numbers. The relative ordering across tiers is more robust than any single number.

5. **No formal proof.** The boundary intelligence hypothesis is empirically grounded but not formally proven. Conditions under which it should fail are stated above.

## 6. What This Doesn't Claim

- That a learned classifier *can't* beat keywords. Only that in our testing it didn't, and that the deployment-complexity tax of a learned model wasn't justified by the marginal accuracy.
- That 49% is a guarantee. Different workloads will have different routing fractions and therefore different savings.
- That this generalizes beyond LLM API routing. The broader boundary-mechanism hypothesis is tested in two other domains in the parent paper, but each domain is a separate empirical claim.

## 7. Reproducing the Results

The classifier source is at `governor/router.py`. The pricing model is at `governor/pricing.py`. The 35-turn measurement methodology is in the parent paper (§5.3 of the full synthesis).

To reproduce on your own workload:

1. Run your normal LLM workload through Governor (`governor serve`) for a week
2. Compare `/v1/usage` totals against your would-have-been spend on a single frontier model
3. Hand-rate ~30 randomly-sampled completions from each tier blind to source

The savings number that comes out is your savings number — not ours.

## 8. Citation

If you reference this work, please cite as:

> Moon, B. (2026). *Boundary Mechanisms for Efficient AI Systems: Findings from a Multi-Project Research Program*. §5 (Governor Routing). Independent research preprint.

The full synthesis paper is the canonical reference; this document is an extract.
