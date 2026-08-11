# Governor: Workload-Classifying Proxy for LLM APIs

**Bentley Moon**
April 2026

> This is a public-facing extract of §5 ("Finding 3: Governor Routing") from a longer research synthesis on boundary mechanisms in AI systems. The full synthesis covers two additional findings — the multi-file wall in LLM code repair, and momentum protection in continual learning under metabolic energy constraint — alongside fourteen documented neural-module negative results.

## Abstract

Governor is a 3-tier classifier and proxy that routes LLM API requests to the cheapest tier whose quality is adequate for the workload. Across 35 measured turns spanning coding, debugging, research, and customer-support sessions, Governor produced **49% cost reduction on mixed coding and 65% on debugging**, with 95–96% hand-rated quality retention, computed against simulated cloud pricing on published model rate cards.

> **Correction, 2026-08-11.** This abstract previously reported a "23–65%" range. No measurement in this
> work produced 23%, and the public README reported a third range, "30-60%", which also matches no
> measurement. The four measured values are 49%, 65%, 92% and 93%. Only the per-scenario figures are
> reported now.

The classifier itself is approximately 200 lines of keyword regex with no learned components, no embeddings, and no internal state model. The argument for keywords over a learned classifier is a **hypothesis carried over from the parent research program, not a result established here**: the decision-relevant signal for tier selection appears to be observable at the request boundary, in the words of the prompt.

> **Correction, 2026-08-11.** This paragraph previously stated that "a more sophisticated classifier did
> not improve the routing decision in our testing." No such classifier was ever tested.
> `MASTER_RESEARCH_PAPER.md` §7 records "N/A (no internal model tested)" for this domain.

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

> **Read this result with suspicion, 2026-08-11.** A perfect 100% detection and 0% false-alarm score, on
> attacks and valid proposals both authored by the same person who wrote the validator, is the signature
> of an instrument that is not discriminating rather than one that is discriminating perfectly. There is
> no canary here: no deliberately broken case the validator must fail to catch, which is the only way to
> tell "caught everything" apart from "flagged everything" or "never looked." A sibling program in this
> research ecosystem retracted 30 graded results to exactly this failure. Until a canary and a negative
> control are added, treat §3 as unvalidated and do not cite it.

## 4. Why a Regex Is Enough (the boring argument)

The hypothesis from the broader research program is that **boundary mechanisms outperform internal models when the sufficient statistic for the decision is observable at the system-environment interface.**

For tier selection, the hypothesis is that the sufficient statistic is the presence of coding/architecture keywords in the prompt, observable at the request boundary. A learned classifier could in principle do better. **We do not know whether it does, because we never ran one.**

This is not a weak claim, it is an untested one, and the distinction matters. What this work shows is what a regex achieves on its own on 35 turns. It shows nothing about how that compares to a learned router. The hypothesis predicts failure modes:

- Workloads where complexity depends on context not present in the current turn (long-running negotiations, multi-document reasoning where the keywords are in the documents, not the prompt)
- Workloads where the relevant tier depends on the *response* the LLM will produce, not the request (creative work, planning)
- Non-English workloads (the keyword list is English-coding-centric)

These are all extension targets, not refutations. The regex-is-enough claim is bounded to the workloads tested.

## 5. Limitations

1. **Sample size, and no published data.** Quality measurement is on 35 hand-rated turns, roughly nine per scenario, reported above to three-decimal dollar precision. The turn-level data (prompts, assigned tier, computed cost, rating) is **not published anywhere, including in the parent paper**, so no reader can currently check these figures. Re-validate on your own workload.

2. **The baseline is disputed within our own documents.** This paper labels the comparator "Flat (frontier model)"; `MASTER_RESEARCH_PAPER.md` §5.3 labels the identical dollar figures "Flat (all capable model)". Those are different counterfactuals and cannot both be right. Until the turn-level data is published, treat the savings as measured against *some* single-model baseline of unconfirmed tier. Note also that routing every turn, greetings included, to one expensive model is the most favourable possible comparator.

2. **Simulated costs.** Pricing is computed from published cloud rate cards. Customers with negotiated direct rates from OpenAI/Anthropic will see smaller savings.

3. **English-coding-centric.** The keyword list reflects the workloads tested. Non-English deployments will need keyword extension.

4. **Quality measurement is human-rated.** Different raters will produce different absolute numbers. The relative ordering across tiers is more robust than any single number.

5. **No formal proof.** The boundary intelligence hypothesis is empirically grounded but not formally proven. Conditions under which it should fail are stated above.

## 6. What This Doesn't Claim

- That a learned classifier *can't* beat keywords, or that it doesn't. **No learned classifier was tested.** This work is silent on that comparison in both directions, and any earlier wording here suggesting otherwise was wrong.
- That 49% is a guarantee. Different workloads will have different routing fractions and therefore different savings.
- That this generalizes beyond LLM API routing. The broader boundary-mechanism hypothesis is tested in two other domains in the parent paper, but each domain is a separate empirical claim.

## 7. Reproducing the Results

The classifier source is at `governor/router.py`. The pricing model is at `governor/pricing.py`.

**The 35-turn measurement methodology is not published.** An earlier version of this section pointed readers to "§5.3 of the full synthesis." That section contains the same four-row results table reproduced above and no method: no turn selection procedure, no prompts, no model identities, no rating protocol. The pointer was circular. Until the turn-level data is released, the figures in this document cannot be independently checked and should be read as indicative.

To reproduce on your own workload:

1. Run your normal LLM workload through Governor (`governor serve`) for a week
2. Compare `/v1/usage` totals against your would-have-been spend on a single frontier model
3. Hand-rate ~30 randomly-sampled completions from each tier blind to source

The savings number that comes out is your savings number — not ours.

## 8. Citation

If you reference this work, please cite as:

> Moon, B. (2026). *Boundary Mechanisms for Efficient AI Systems: Findings from a Multi-Project Research Program*. §5 (Governor Routing). Independent research preprint.

The full synthesis paper is the canonical reference; this document is an extract.
