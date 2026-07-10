# Prototype Parity Contract Tests

This directory preserves observable Merida prototype behavior for the proposed final-app migration.

## Test seam

Fixtures run through public Capture, Application Analysis, and Resume Creation workflow interfaces. Recording fakes replace system boundaries such as Notion, DeepSeek, time, and PDF storage. Capture Evidence normalization is the only narrower supporting seam.

Tests assert typed outcomes, semantic effects, safety-critical effect order, and cleanup residue. They do not freeze prototype HTTP paths, backend-rendered HTML, NDJSON framing, process topology, exact model prose, or PDF bytes.

## Files

- `fixtures/prototype-parity.v1.json` is the machine-readable, versioned corpus.
- `parityContract.js` loads and validates the corpus.
- `prototypeHarness.js` runs executable observations against the working prototype.
- `prototypeParity.test.js` automatically exercises every fixture marked `prototypeExecutable`.
- `.scratch/proposed-final-app/assets/prototype-parity-inventory.md` is the human-readable classification and coverage audit.

## Adding a fixture

1. Give the fixture a stable domain-oriented ID.
2. Classify it as `parity_required`, `superseded`, `target_addition`, `known_defect`, or `deferred`.
3. Record its evidence sources, action, initial state, deterministic boundary outputs, expected outcome, effects, forbidden effects, cleanup residue, and policy versions.
4. For an executable prototype observation, add or extend the smallest workflow-owned observer runner needed to make the corpus-driven test green.
5. Add the fixture to the human inventory so the synchronization test stays green.

Run only this contract suite with:

```sh
node --test test/parity/*.test.js
```
