# ArchForge — 10 Residential End-to-End Scenarios

This file is the permanent change/fix log requested for the residential integration campaign.

## Validation rule

Each scenario is processed strictly in this order and the run stops on the first failure:

1. Architectural/design model
2. Structural model + analysis
3. MEP: water supply, drainage, electrical circuits and cable routing
4. Project commercial quote
5. Human-openable `.archforge` fixture remains in this folder

A software pass does **not** certify engineering rules. Existing `ENGINEER_REVIEW`, `UNVERIFIED`, `DESIGN_DEFAULT` and provenance statuses remain authoritative.

The `price_list` inside these fixtures uses synthetic `1.00` test values solely to exercise the pricing pipeline. They are explicitly named `TEST_FIXTURE prices — not market data` and are not real construction prices.

## Scenarios

- S01 — Aegean Courtyard Duplex
- S02 — Split-Level Hillside House
- S03 — Three-Storey Urban Residence
- S04 — Lakeside Family Villa
- S05 — Compact Stepped Townhouse
- S06 — Wide Mediterranean Villa
- S07 — Narrow Three-Level House
- S08 — Terraced Slope Residence
- S09 — Courtyard Roof Variety House
- S10 — Full-System Family Residence

## Changes introduced before first run

- Added deterministic 10-scenario manifest.
- Added deterministic generator for project files.
- Added sequential E2E test which stops at the first broken scenario/stage.
- Added CI workflow which generates and commits the `.archforge` fixtures to the test branch, then runs the scenario suite.
- No production ArchForge behavior has been changed yet. Production fixes will be listed below only when a scenario exposes a real defect.

## Defects / fixes

Pending first CI run.
