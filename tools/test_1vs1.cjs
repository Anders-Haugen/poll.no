const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { join } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const { matchShooterProfiles } = runInNewContext(
  `${readFileSync(join(__dirname, "..", "1vs1.js"), "utf8")}\n({ matchShooterProfiles });`
);

const shooter = { id: "local", name: "Test Skyttar", club: "Test", clubId: "100" };
const profile = { shooter: "Test Skyttar", club: "Test Skytterlag", shooterId: "123" };

test("matches only name and club, allowing whitespace, case and club suffix", () => {
  const matches = matchShooterProfiles([shooter], [
    { ...profile, shooter: "  TEST   SKYTTAR " },
    { shooter: "Someone Else", club: "Test", shooterId: "456" },
  ]);
  assert.equal(matches.get("local"), "123");
  assert.equal(matchShooterProfiles([shooter], [{ ...profile, club: "Other" }]).size, 0);
});

test("conflicting IDs and duplicate local identities are not linked", () => {
  assert.equal(matchShooterProfiles([shooter], [profile, { ...profile, shooterId: "456" }]).size, 0);
  assert.equal(matchShooterProfiles([shooter, { ...shooter, id: "duplicate", clubId: "200" }], [profile]).size, 0);
  assert.equal(matchShooterProfiles([shooter], [profile, profile]).get("local"), "123");
});

test("invalid IDs are rejected rather than used as image or link URLs", () => {
  for (const shooterId of ["", "0", "../image", "123.jpg", 123]) {
    assert.throws(() => matchShooterProfiles([shooter], [{ ...profile, shooterId }]), /Ugyldig skytterprofil/);
  }
});
