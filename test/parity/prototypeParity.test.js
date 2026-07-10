import test from "node:test";
import assert from "node:assert/strict";
import { loadParityInventory } from "./parityContract.js";
import { runPrototypeObservation } from "./prototypeHarness.js";

test("every executable prototype fixture matches its versioned observation", async (t) => {
  const fixtures = loadParityInventory().fixtures.filter((fixture) => fixture.prototypeExecutable);

  for (const fixture of fixtures) {
    await t.test(`${fixture.id}: ${fixture.title}`, async () => {
      assert.deepEqual(await runPrototypeObservation(fixture), {
        outcome: fixture.observation.expectedOutcome,
        effects: fixture.observation.expectedEffects,
        state: fixture.observation.expectedState,
        callCounts: fixture.observation.expectedCallCounts,
        cleanupResidue: fixture.observation.cleanupResidue,
      });
    });
  }
});
