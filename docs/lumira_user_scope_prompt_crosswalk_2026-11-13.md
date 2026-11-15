# User-supplied Lumira scope prompt crosswalk

Date: 2026-11-13
Source: Library file `Pasted text(20261113-124835).txt`, section 9 (Approved Lumira Capability Scope), recovered and read during this continuation.

## Source verification

- The recovered source contains domains A–U exactly as shown below.
- A direct parse of section 9 counted **428 dash-bullet requirements** across 21 domains. The per-domain counts in the table were checked against the source text.
- The older 42-part prompt headings were also checked: A maps to Parts 4–5, B–S map sequentially to Parts 6–23, T maps to Parts 24–29, and U maps to Parts 30–42.
- This verifies the source count and domain-to-part crosswalk. It does not establish one-to-one canonical requirement identity, implementation status, or acceptance evidence.

## Source recovery result

- Captured **428 atomic bullet statements** across **21 approved domains (A–U)**.
- These are source statements, not claims of implementation or verification.
- The crosswalk below maps source domains to the existing PART-1–PART-42 scope parents. It does not yet resolve duplicates against the 99 legacy capability records, 30 feature-area records, or 173 existing prompt subrequirement rows.
- Do not add these 428 statements as new canonical requirements until duplicate/alias reconciliation is complete.

## Domain-to-section crosswalk

| Source | Domain | Bullet statements | Candidate existing scope parents |
|---|---|---:|---|
| 9.A | Core brain and intelligence | 16 | PART-4, PART-5 |
| 9.B | Model and provider management | 12 | PART-6 |
| 9.C | Memory and knowledge | 18 | PART-7 |
| 9.D | Personal knowledge library | 13 | PART-8 |
| 9.E | Multi-agent intelligence | 22 | PART-9 |
| 9.F | Workflow and automation | 14 | PART-10 |
| 9.G | Autonomous software development | 33 | PART-11 |
| 9.H | Research system | 15 | PART-12 |
| 9.I | Voice intelligence | 19 | PART-13 |
| 9.J | Creation Studio | 21 | PART-14 |
| 9.K | Personal assistant | 14 | PART-15 |
| 9.L | Desktop intelligence | 14 | PART-16 |
| 9.M | Security and autonomy | 19 | PART-17 |
| 9.N | Learning and self-improvement | 11 | PART-18 |
| 9.O | Artifact management | 14 | PART-19 |
| 9.P | Device and IoT intelligence | 17 | PART-20 |
| 9.Q | Robotics intelligence | 16 | PART-21 |
| 9.R | Electronics and engineering intelligence | 20 | PART-22 |
| 9.S | Plugin ecosystem | 18 | PART-23 |
| 9.T | Internal infrastructure | 43 | PART-24, PART-25, PART-26, PART-27, PART-28, PART-29 |
| 9.U | External machinery | 59 | PART-30, PART-31, PART-32, PART-33, PART-34, PART-35, PART-36, PART-37, PART-38, PART-39, PART-40, PART-41, PART-42 |

## Mapping rules

1. Preserve the exact user-supplied bullet wording when creating atomic source records.
2. Treat candidate existing scope parents as provisional crosswalks, not verified dependency edges.
3. Match each source bullet to an existing canonical requirement ID where equivalent; retain one canonical requirement and record all source aliases.
4. Create a new canonical requirement only when no existing row expresses the same acceptance obligation.
5. For every canonical row, map implementation files, tests, external dependencies, security class, acceptance criteria, evidence, blockers and effort weight.
6. Keep external machinery requirements separate from software build work; do not count hardware acquisition as building completion.
7. Never promote a row to VERIFIED from source mapping alone.

## Immediate next mapping actions

- Reconcile A–F against PART-4–PART-10 and the 173 existing atomic rows.
- Reconcile G–S against PART-11–PART-23.
- Reconcile T against PART-24–PART-29.
- Reconcile U against PART-30–PART-42 and classify physical hardware/provider requirements as external dependencies or acceptance gates.
- Update the authoritative JSON ledger only after duplicate decisions are recorded and schema validation passes.

## Status

**Source capture: complete for section 9 A–U.**
**Canonical duplicate reconciliation: not yet complete.**
**Requirement-level code/test/dependency/security mapping: not yet complete.**
**No implementation status or completion percentage is changed by this crosswalk.**


## Candidate reconciliation pass ? 2026-11-13

- Preserved all 428 exact source bullets in docs/lumira_source_scope_requirements_2026-11-13.json.
- Generated lexical candidate report docs/lumira_source_scope_reconciliation_candidates_2026-11-13.json against the 349 existing ledger rows.
- Candidate distribution: 49 exact normalized-name matches, 361 lexical review candidates, and 18 with no strong name candidate. These are not canonical mapping decisions.
- Multiple existing IDs share exact normalized names in some cases, requiring explicit duplicate/alias review.
- No automatic merges, canonical rows, status changes or completion percentages were applied.
- Domain U remains external machinery and must be separated from software build-only effort.
- Detailed audit: docs/lumira_source_scope_reconciliation_report_2026-11-13.md.


## Full 42-part master prompt recovery ? 2026-11-13

- Recovered the earlier full master prompt from Pasted text(20261112-150057).txt.
- The prompt contains two copies with identical PART-4?PART-42 numbered build lists; one copy was retained.
- Extracted 727 numbered build requirements and 9 specialist-agent coverage subitems; 97 additional governance/process/acceptance items were separately captured.
- Existing 173 atomic ledger rows: 162 exact unique matches to the recovered 727 requirements; 11 remain for semantic review.
- Newer section-9 A?U bullets to recovered 727: 148 exact wording matches, 129 strong lexical candidates, 136 possible candidates, 15 with no strong candidate.
- Candidate matches are not accepted semantic equivalence. No new canonical rows were added and no status was promoted by this mapping pass.
- The canonical denominator remains unfrozen pending full semantic reconciliation of the overlapping sources.
