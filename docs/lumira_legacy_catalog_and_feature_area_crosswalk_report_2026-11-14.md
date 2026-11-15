# Legacy catalog and approved feature-area crosswalk — 2026-11-14

## Scope

- 727 numbered requirements from the recovered PART-4–PART-42 master prompt.
- 99 legacy capability catalog records from the existing product completion matrix lineage.
- 30 approved feature areas from the current product completion matrix.

## Candidate-generation and review results

The generated file `lumira_legacy_catalog_and_feature_area_crosswalk_candidates_2026-11-14.json` contains candidate parent sections and atomic requirements for each legacy catalog record and approved feature area.

| Source set | Exact phrase confirmed | Strong lexical | Possible lexical | Weak lexical | No candidate |
|---|---:|---:|---:|---:|---:|
| Legacy catalog (99) | 44 | 34 | 21 | 0 | 0 |
| Approved feature areas (30) | 1 | 14 | 12 | 1 | 2 |

### Confirmed legacy aliases

- 44 legacy capability names match one unique master-prompt atomic requirement after only case and punctuation normalization.
- These 44 source references were attached to their canonical prompt rows as `EXACT_TEXT_ALIAS_CONFIRMED` aliases.
- All 44 targets are unique. The original legacy catalog records remain in the ledger for traceability.
- The remaining 55 legacy catalog records are still unresolved; lexical candidates are not treated as aliases.

## Interpretation and restrictions

- Lexical scores are retrieval hints, not probabilities of semantic equivalence.
- Approved feature areas are broad product-level groupings. A feature area can cover many atomic requirements and must not be collapsed into its top-scoring child.
- Some weak or no-candidate feature areas may be covered by differently worded requirements, multiple requirements, or separate implementation scope. They require manual review against the original wording and product matrix.
- No ledger rows were merged or deleted. No implementation statuses changed. The 914-record ledger and its status counts are unchanged. The canonical denominator remains unfrozen and full-scope reconciliation remains false.

## Next work

1. Human-review the remaining 55 legacy records, especially broad labels and cross-domain capabilities.
2. Map each of the 30 feature areas to the full set of relevant atomic requirements, not just one top candidate.
3. Reconcile the 428 latest A–U bullets and 97 governance items into a final source-of-truth map.
4. Only after the semantic decisions are recorded, freeze the canonical build denominator and calculate completion from verified implementation evidence.
