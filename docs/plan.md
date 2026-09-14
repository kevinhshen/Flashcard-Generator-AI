# Plan

## Completed rules-only foundation

- Remove former cloud-runtime artifacts and dependencies
- Separate parsing, card generation, validation, export, and CLI concerns
- Preserve paragraph boundaries and prevent cross-chunk cards
- Add regression tests and TSV export

## Before FLAN-T5

1. Review cards from `note1.txt` through `note4.txt` and record 20–30 representative source chunks.
2. Label whether each expected card is useful, duplicate, unsupported, or missing.
3. Keep improving rules only where the correction is deterministic.

## FLAN-T5 milestone

1. Add a lazy `FlanT5Generator` behind a small backend interface.
2. Compare rules-only, FLAN-only, and hybrid outputs using the reviewed evaluation set.
3. Track valid-card rate, duplicate rate, source support, and accept/edit/delete rate.
4. Add a review step before export.
