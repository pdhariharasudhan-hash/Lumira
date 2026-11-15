# Lumira source-scope reconciliation audit ? 2026-11-13

## Source capture
- Parsed the user-provided section 9 A?U into 428 exact source bullet records across 21 domains.
- Preserved source wording and assigned stable source IDs in docs/lumira_source_scope_requirements_2026-11-13.json.
- Existing canonical ledger remains 349 records; its rows were not merged or deleted.

## Candidate matching results
- Exact normalized-name candidates: **49** source bullets.
- Lexical review candidates: **361** source bullets.
- No strong lexical candidate: **18** source bullets.
- Exact-name cases with multiple existing IDs: **8**; these require duplicate/alias decisions.
- Candidate scoring uses normalized names and lexical similarity. It is not semantic equivalence and is not evidence of implementation.

## Domain breakdown

| Domain | Source bullets | Exact name | Review candidates | No strong candidate |
|---|---:|---:|---:|---:|
| A | 16 | 4 | 12 | 0 |
| B | 12 | 5 | 7 | 0 |
| C | 18 | 9 | 9 | 0 |
| D | 13 | 4 | 9 | 0 |
| E | 22 | 4 | 18 | 0 |
| F | 14 | 4 | 10 | 0 |
| G | 33 | 3 | 29 | 1 |
| H | 15 | 1 | 14 | 0 |
| I | 19 | 2 | 16 | 1 |
| J | 21 | 3 | 16 | 2 |
| K | 14 | 2 | 12 | 0 |
| L | 14 | 0 | 14 | 0 |
| M | 19 | 0 | 19 | 0 |
| N | 11 | 2 | 9 | 0 |
| O | 14 | 0 | 13 | 1 |
| P | 17 | 0 | 17 | 0 |
| Q | 16 | 4 | 12 | 0 |
| R | 20 | 0 | 20 | 0 |
| S | 18 | 1 | 16 | 1 |
| T | 43 | 1 | 39 | 3 |
| U | 59 | 0 | 50 | 9 |

## Decisions and boundaries
- No automatic canonical merges were performed.
- No canonical requirement statuses or completion percentages were changed.
- Existing parent/area/catalog records are not treated as equivalent to atomic acceptance obligations solely because names are similar.
- Domain U is external machinery. Physical equipment acquisition and hardware-in-loop acceptance are external dependencies, not software coding completion. Software/runtime/provider dependencies inside U must be classified individually.
- Domains A?T are candidate software/system scope, but each bullet still needs an acceptance obligation, source/test mapping, dependencies, security classification, effort weight and evidence.

## Remaining mapping work
1. Human-review all 428 candidate matches and identify true duplicates versus related-but-distinct obligations.
2. Reconcile the 18 no-strong-candidate items and all U machinery requirements.
3. Decompose remaining master prompt Parts 1?3 and 11?42 using authoritative nested source text, not inferred headings.
4. Map canonical rows to actual implementation files, test evidence, external dependencies and threat-model controls.
5. Only then freeze the unique canonical denominator and calculate build-only effort weights.

**Mapping status: source capture complete; candidate generation complete; canonical reconciliation and acceptance mapping incomplete.**


## Recovery of the authoritative 42-part master prompt ? 2026-11-13

The earlier master prompt was recovered from the Library file Pasted text(20261112-150057).txt. It contains two full copies of the same prompt; the PART-4?PART-42 numbered requirement lists in both copies were compared and matched exactly. One canonical source copy was retained.

- PART-4 through PART-42 contain **727 numbered build requirements** plus **9 specialist-agent coverage subitems** in PART-9.
- PART-2/3, PART-8/9/10/11 governance and acceptance requirements were separately extracted as **97 governance items**.
- Added source files:
  - docs/lumira_master_prompt_atomic_requirements_2026-11-13.json
  - docs/lumira_master_prompt_governance_requirements_2026-11-13.json
- Crosswalked the existing 173 atomic prompt ledger rows against the 727 source items within the same PART: **162 exact unique matches**, 8 possible lexical matches and 3 with no strong match. Exact aliases were attached to those 162 ledger rows; 11 rows remain for semantic review.
- Crosswalked the 428 latest section-9 A?U bullets against the 727 older prompt requirements within the documented domain-to-part pools: **148 exact wording matches** (including two camera entries disambiguated by their electronics/robotics subdomain), 129 strong lexical candidates, 136 possible candidates and 15 with no strong match.
- Exact aliases do not prove implementation or acceptance. Lexical candidates are not accepted mappings.
- The 349-row ledger remains unchanged in row count and status: 64 IMPLEMENTED, 256 IN_PROGRESS, 27 BLOCKED, 1 NOT_STARTED, 1 VERIFIED. Counts are internally consistent.
- Full semantic deduplication across the 727 requirements, 428 newer bullets, 99 legacy catalog entries, 30 approved areas, 173 atomic prompt rows and 46 parent records is not complete. The unique canonical denominator is not frozen and no overall/build-only percentage is asserted.


## Atomic source-ledger expansion ? 2026-11-13
- Added all **727** numbered build requirements from the recovered PART-4?PART-42 master prompt to the authoritative ledger.
- Reused **162** exact unique matches from the prior 173 atomic prompt rows; created **565** new source-backed atomic rows. The remaining **11** pre-existing prompt rows are retained as additional obligations pending semantic review.
- Added **148** exact aliases from the newer section-9 A?U scope to their corresponding canonical ledger rows.
- Linked each PART-4?PART-42 parent to its atomic child IDs. Source capture is complete; implementation, dependencies, tests, external prerequisites, security classification and acceptance remain to be audited for the new rows.
- Added tests/test_lumira_requirement_inventory.py; **6 passed in 0.46s**. The tests validate source counts, canonical row coverage, parent-child links, exact aliases, ledger counts and the explicit not-reconciled state.
- Current ledger: **914 records** ? 64 IMPLEMENTED, 821 IN_PROGRESS, 27 BLOCKED, 1 NOT_STARTED, 1 VERIFIED. The 727 source requirements are represented, but the unique denominator is not frozen because the 99 legacy capability entries, 30 approved feature areas, 46 parent records and 428 newer scope statements still need semantic deduplication.
- No implementation status was promoted by the source-ledger expansion. No overall or building-only completion percentage is asserted.
