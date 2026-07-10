import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

test("extension action opens the persistent side panel instead of a popup", async () => {
  const manifest = JSON.parse(
    await readFile(new URL("../extension/manifest.json", import.meta.url), "utf8"),
  );

  assert.equal(manifest.icons["16"], "icons/bownarrow-16.png");
  assert.equal(manifest.icons["32"], "icons/bownarrow-32.png");
  assert.equal(manifest.icons["48"], "icons/bownarrow-48.png");
  assert.equal(manifest.icons["128"], "icons/bownarrow-128.png");
  assert.equal(manifest.action.default_icon["16"], "icons/bownarrow-16.png");
  assert.equal(manifest.action.default_icon["32"], "icons/bownarrow-32.png");
  assert.equal(manifest.action.default_icon["48"], "icons/bownarrow-48.png");
  assert.equal(manifest.action.default_icon["128"], "icons/bownarrow-128.png");
  assert.equal(manifest.side_panel.default_path, "popup.html");
  assert.equal(manifest.background.service_worker, "background.js");
  assert.equal(manifest.action.default_popup, undefined);
  assert.ok(manifest.permissions.includes("sidePanel"));
});

test("extension icon files are packaged from the user-provided bownarrow image", async () => {
  for (const size of ["16", "32", "48", "128"]) {
    const icon = await readFile(
      new URL(`../extension/icons/bownarrow-${size}.png`, import.meta.url),
    );

    assert.equal(icon[0], 0x89);
    assert.equal(icon.toString("ascii", 1, 4), "PNG");
  }
});

test("extension opens the side panel from an explicit action click", async () => {
  const backgroundScript = await readFile(
    new URL("../extension/background.js", import.meta.url),
    "utf8",
  );

  assert.match(backgroundScript, /chrome\.action\.onClicked\.addListener/);
  assert.match(backgroundScript, /chrome\.sidePanel\.open/);
  assert.doesNotMatch(backgroundScript, /openPanelOnActionClick/);
  assert.doesNotMatch(backgroundScript, /async function openCapturePanel/);
  assert.doesNotMatch(backgroundScript, /function openCapturePanel[\s\S]*?chrome\.sidePanel\.setOptions[\s\S]*?chrome\.sidePanel\.open/);
});

test("extension pages use the bownarrow PNG favicon", async () => {
  const popupHtml = await readFile(
    new URL("../extension/popup.html", import.meta.url),
    "utf8",
  );
  const optionsHtml = await readFile(
    new URL("../extension/options.html", import.meta.url),
    "utf8",
  );

  assert.match(popupHtml, /rel="icon" href="icons\/bownarrow-32\.png"/);
  assert.match(optionsHtml, /rel="icon" href="icons\/bownarrow-32\.png"/);
});

test("extension has a parse-only fill form action without direct capture", async () => {
  const popupHtml = await readFile(
    new URL("../extension/popup.html", import.meta.url),
    "utf8",
  );
  const popupScript = await readFile(
    new URL("../extension/popup.js", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(popupHtml, /id="captureButton"/);
  assert.match(popupHtml, /id="fillFormButton"/);
  assert.doesNotMatch(popupScript, /captureButton/);
  assert.match(popupScript, /fillFormButton\.addEventListener/);
  assert.match(popupScript, /postJson\(config, "\/parse", evidence\)/);
  assert.doesNotMatch(popupScript, /postJson\(config, "\/capture", evidence\)/);
  assert.match(popupScript, /buildCaptureEvidencePayload\(injections, tab\.url\)/);
  assert.doesNotMatch(popupScript, /function mergeFrameEvidence/);
});
