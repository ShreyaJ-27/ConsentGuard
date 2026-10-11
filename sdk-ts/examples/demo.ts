import { ConsentGuard, ConsentGuardApiError } from "../src/index";

async function runDemo(): Promise<void> {
  const apiKey = process.env.CONSENTGUARD_API_KEY || "demo-api-key-01234567890123456789";
  const baseUrl = process.env.CONSENTGUARD_URL || "http://127.0.0.1:8000";

  console.log("=== ConsentGuard TypeScript SDK Integration Demo ===");
  const cg = new ConsentGuard({ apiKey, baseUrl });

  // 1. Request check
  console.log("\n[1] Submitting request check to /v1/check...");
  const check = await cg.check({
    prompt: "Apply a subtle vintage photo filter",
    scope: "filter",
    userRef: "user_demo_42",
  });
  console.log(`Check ID: ${check.checkId}`);
  console.log(`Decision: ${check.decision} (Tier: ${check.tier})`);

  if (check.decision === "needs_consent") {
    console.log("Consent required. In production, prompt subject for passkey/selfie verification.");
    return;
  }

  if (check.decision === "block") {
    console.log(`Request blocked by safety policy. Reasons: ${check.reasons.join(", ")}`);
    return;
  }

  // 2. Simulated partner generation (creates harmless demo image in memory)
  console.log("\n[2] Partner model generates harmless demo output...");
  // Tiny valid 1x1 PNG image fixture
  const demoPngBytes = new Uint8Array([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
    0x0d, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x60, 0x60, 0x60, 0x60,
    0x00, 0x00, 0x00, 0x05, 0x00, 0x01, 0xa7, 0x35, 0x47, 0x24, 0x00, 0x00,
    0x00, 0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
  ]);

  // 3. Stamping output
  console.log("\n[3] Running output safety checks and provenance stamping...");
  const receipt = await cg.stamp({
    checkId: check.checkId,
    image: demoPngBytes,
    filename: "vintage_output.png",
  });

  console.log("Provenance Receipt received:");
  console.log(`- Entry ID:          ${receipt.entryId}`);
  console.log(`- Output SHA-256:    ${receipt.outputSha256}`);
  console.log(`- Pre-stamp SHA-256: ${receipt.preStampSha256}`);
  console.log(`- Perceptual Hash:   ${receipt.phash}`);
  console.log(`- Visible Label:     ${receipt.label}`);
  console.log(`- Ledger Hash:       ${receipt.ledgerEntryHash}`);
  if (receipt.outputRef) {
    console.log(`- Output Reference:  ${receipt.outputRef}`);
  }

  // 4. Ledger origin lookup
  console.log("\n[4] Querying provenance ledger by perceptual hash...");
  const lookup = await cg.lookup(receipt.phash);
  console.log(`Lookup Match: ${lookup.match} (method: ${lookup.method})`);
  if (lookup.provenance) {
    console.log(`Found check ID: ${lookup.provenance.checkId}, stamped at ${lookup.provenance.createdAt}`);
  }

  // 5. Demonstrate defensive rejection
  console.log("\n[5] Demonstrating defensive fail-closed rejection on flagged output...");
  try {
    await cg.stamp({
      checkId: check.checkId,
      image: demoPngBytes,
      mockSignal: "flagged",
    });
    console.error("ERROR: Flagged output was unexpectedly allowed!");
  } catch (err) {
    if (err instanceof ConsentGuardApiError) {
      console.log(`Successfully blocked flagged output (HTTP ${err.statusCode}: ${err.errorCode})`);
    } else {
      throw err;
    }
  }

  console.log("\n=== Demo completed successfully ===");
}

if (require.main === module) {
  runDemo().catch((err) => {
    console.error("Demo failed:", err);
    process.exit(1);
  });
}
