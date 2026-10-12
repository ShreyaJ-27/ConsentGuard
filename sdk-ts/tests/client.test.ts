import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  ConsentGuard,
  ConsentGuardApiError,
  ConsentGuardError,
  ConsentGuardNetworkError,
  ConsentGuardTimeoutError,
} from "../src/index";

const TEST_API_KEY = "test-secret-api-key-0123456789012345";

describe("ConsentGuard SDK Client", () => {
  it("fails initialization without valid apiKey", () => {
    assert.throws(() => new ConsentGuard({ apiKey: "" }), ConsentGuardError);
    assert.throws(() => new ConsentGuard({ apiKey: "   " }), ConsentGuardError);
  });

  it("serializes check request and parses response successfully", async () => {
    let capturedUrl = "";
    let capturedHeaders: Record<string, string> = {};
    let capturedBody: any = null;

    const mockFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      capturedUrl = String(input);
      capturedHeaders = (init?.headers as any) || {};
      capturedBody = JSON.parse(String(init?.body));

      const responsePayload = {
        check_id: "c_abc123",
        decision: "allow",
        tier: 0,
        reasons: ["benign_edit"],
        consent_required: false,
        request_risk: {
          score: 0.05,
          label: "low",
          source: "stub",
        },
      };

      return new Response(JSON.stringify(responsePayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      baseUrl: "https://api.consentguard.test",
      fetch: mockFetch as any,
    });

    const res = await client.check({
      prompt: "Apply subtle color adjustment",
      scope: "filter",
      userRef: "user_42",
      testSignals: { real_face: false, minor_risk: false },
      targetRef: "opaque-target-17",
      consentToken: "token-value",
      consentCheckId: "c_consent_parent",
    });

    assert.equal(capturedUrl, "https://api.consentguard.test/v1/check");
    assert.equal(new Headers(capturedHeaders).get("X-API-Key"), TEST_API_KEY);
    assert.equal(capturedBody.prompt, "Apply subtle color adjustment");
    assert.equal(capturedBody.scope, "filter");
    assert.equal(capturedBody.user_ref, "user_42");
    assert.equal(capturedBody.target_ref, "opaque-target-17");
    assert.equal(capturedBody.consent_token, "token-value");
    assert.equal(capturedBody.consent_check_id, "c_consent_parent");
    assert.deepEqual(capturedBody.test_signals, { real_face: false, minor_risk: false });

    assert.equal(res.checkId, "c_abc123");
    assert.equal(res.decision, "allow");
    assert.equal(res.tier, 0);
    assert.deepEqual(res.reasons, ["benign_edit"]);
    assert.equal(res.consentRequired, false);
    assert.equal(res.requestRisk.score, 0.05);
  });

  it("serializes stamp request with FormData and parses receipt", async () => {
    const captured: {
      url: string;
      headers: Headers | null;
      body: FormData | null;
    } = { url: "", headers: null, body: null };

    const mockFetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      captured.url = String(input);
      captured.headers = new Headers(init?.headers);
      captured.body = init?.body as FormData;

      const receiptPayload = {
        check_id: "c_stamp_100",
        entry_id: "entry_demo_001",
        output_sha256: "out_sha_val",
        pre_stamp_sha256: "pre_sha_val",
        phash: "0123456789abcdef",
        label: "AI-generated",
        created_at: "2026-10-11T12:00:00Z",
        ledger_entry_hash: "ledger_entry_hash_val",
        output_ref: "out_demo_001",
      };

      return new Response(JSON.stringify(receiptPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      baseUrl: "https://api.consentguard.test",
      fetch: mockFetch as any,
    });

    const dummyImage = new Uint8Array([1, 2, 3, 4, 5]);
    const receipt = await client.stamp({
      checkId: "c_stamp_100",
      image: dummyImage,
      filename: "test.png",
      mockSignal: "flagged",
      consentToken: "consent-token",
      targetRef: "opaque-target",
    });

    assert.equal(captured.url, "https://api.consentguard.test/v1/output/stamp");
    assert.equal(captured.headers?.get("X-API-Key"), TEST_API_KEY);
    assert.equal(captured.body?.get("check_id"), "c_stamp_100");
    assert.equal(captured.body?.get("mock_signal"), "flagged");
    assert.equal(captured.body?.get("consent_token"), "consent-token");
    assert.equal(captured.body?.get("target_ref"), "opaque-target");
    assert.equal(captured.body?.has("high_risk"), false);
    assert.equal(receipt.checkId, "c_stamp_100");
    assert.equal(receipt.entryId, "entry_demo_001");
    assert.equal(receipt.outputSha256, "out_sha_val");
    assert.equal(receipt.preStampSha256, "pre_sha_val");
    assert.equal(receipt.phash, "0123456789abcdef");
    assert.equal(receipt.label, "AI-generated");
    assert.equal(receipt.outputRef, "out_demo_001");
  });

  it("converts non-2xx responses into typed ConsentGuardApiError", async () => {
    const mockFetch = async (): Promise<Response> => {
      const errorBody = {
        error: {
          code: "harmful_content_detected",
          message: "Output failed safety verification: harmful content detected.",
        },
      };
      return new Response(JSON.stringify(errorBody), {
        status: 422,
        headers: { "Content-Type": "application/json" },
      });
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      fetch: mockFetch as any,
    });

    await assert.rejects(
      async () => {
        await client.stamp({
          checkId: "c_test",
          image: new Uint8Array([0, 1, 2, 3]),
        });
      },
      (err: any) => {
        assert(err instanceof ConsentGuardApiError);
        assert.equal(err.statusCode, 422);
        assert.equal(err.errorCode, "harmful_content_detected");
        assert.match(err.message, /harmful content detected/);
        return true;
      }
    );
  });

  it("redacts the API key from gateway error codes as well as messages", async () => {
    const mockFetch = async (): Promise<Response> =>
      new Response(
        JSON.stringify({
          error: {
            code: `invalid-${TEST_API_KEY}`,
            message: `Rejected ${TEST_API_KEY}`,
          },
        }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      fetch: mockFetch as any,
    });

    await assert.rejects(
      async () => client.lookup("0123456789abcdef"),
      (err: any) => {
        assert(err instanceof ConsentGuardApiError);
        assert.doesNotMatch(err.errorCode, new RegExp(TEST_API_KEY));
        assert.doesNotMatch(err.message, new RegExp(TEST_API_KEY));
        assert.doesNotMatch(JSON.stringify(err.details), new RegExp(TEST_API_KEY));
        return true;
      }
    );
  });

  it("handles network failure and wraps in ConsentGuardNetworkError", async () => {
    const mockFetch = async (): Promise<Response> => {
      throw new Error("connect ECONNREFUSED 127.0.0.1:8000");
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      fetch: mockFetch as any,
    });

    await assert.rejects(
      async () => {
        await client.check({
          prompt: "test",
          scope: "filter",
          userRef: "u1",
        });
      },
      (err: any) => {
        assert(err instanceof ConsentGuardNetworkError);
        assert.match(err.message, /Network request failed/);
        return true;
      }
    );
  });

  it("handles request timeout and wraps in ConsentGuardTimeoutError", async () => {
    const mockFetch = async (_: any, init?: RequestInit): Promise<Response> => {
      return new Promise((_, reject) => {
        if (init?.signal) {
          init.signal.addEventListener("abort", () => {
            const abortErr = new Error("This operation was aborted");
            abortErr.name = "AbortError";
            reject(abortErr);
          });
        }
      });
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      timeoutMs: 50,
      fetch: mockFetch as any,
    });

    await assert.rejects(
      async () => {
        await client.lookup("0123456789abcdef");
      },
      (err: any) => {
        assert(err instanceof ConsentGuardTimeoutError);
        assert.equal(err.timeoutMs, 50);
        return true;
      }
    );
  });

  it("keeps the timeout active while consuming a response body", async () => {
    const mockFetch = async (
      _input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> =>
      new Response(
        new ReadableStream({
          start(controller) {
            init?.signal?.addEventListener("abort", () => {
              const abortErr = new Error("The operation was aborted");
              abortErr.name = "AbortError";
              controller.error(abortErr);
            });
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      timeoutMs: 20,
      fetch: mockFetch as any,
    });

    await assert.rejects(
      async () => client.lookup("0123456789abcdef"),
      ConsentGuardTimeoutError
    );
  });

  it("never leaks API key in error messages or string representations", async () => {
    const leakyMessage = `Authorization failed for key: ${TEST_API_KEY}`;
    const mockFetch = async (): Promise<Response> => {
      throw new Error(leakyMessage);
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      fetch: mockFetch as any,
    });

    try {
      await client.check({
        prompt: "test",
        scope: "filter",
        userRef: "u1",
      });
      assert.fail("Expected check() to throw");
    } catch (err: any) {
      assert(err instanceof ConsentGuardNetworkError);
      assert.doesNotMatch(err.message, new RegExp(TEST_API_KEY));
      assert.match(err.message, /\[REDACTED_API_KEY\]/);
      assert.doesNotMatch(String(err), new RegExp(TEST_API_KEY));
    }
  });

  it("correctly queries lookup endpoint and parses match and no-match", async () => {
    let queriedHash = "";
    const mockFetch = async (input: RequestInfo | URL): Promise<Response> => {
      const url = new URL(String(input));
      queriedHash = url.searchParams.get("phash") || "";

      if (queriedHash === "0123456789abcdef") {
        return new Response(
          JSON.stringify({
            match: true,
            method: "exact_phash",
            provenance: {
              check_id: "c_known",
              label: "AI-generated",
              created_at: "2026-10-11T12:00:00Z",
              output_sha256: "known_sha",
            },
          }),
          { status: 200, headers: { "Content-Type": "application/json" } }
        );
      }

      return new Response(
        JSON.stringify({
          match: false,
          method: "exact_phash",
          provenance: null,
          message: "No matching ledger entry found.",
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };

    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      fetch: mockFetch as any,
    });

    const matchRes = await client.lookup("0123456789abcdef");
    assert.equal(matchRes.match, true);
    assert.equal(matchRes.method, "exact_phash");
    assert.equal(matchRes.provenance?.checkId, "c_known");

    const noMatchRes = await client.lookup("ffffffffffffffff");
    assert.equal(noMatchRes.match, false);
    assert.equal(noMatchRes.provenance, null);
    assert.match(noMatchRes.message || "", /No matching/);
  });

  it("downloads output bytes with app authentication", async () => {
    const captured: { url: string; headers: Headers | null } = {
      url: "",
      headers: null,
    };
    const mockFetch = async (
      input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> => {
      captured.url = String(input);
      captured.headers = new Headers(init?.headers);
      return new Response(new Uint8Array([1, 2, 3]), {
        status: 200,
        headers: { "Content-Type": "image/png" },
      });
    };
    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      baseUrl: "https://api.consentguard.test",
      fetch: mockFetch as any,
    });

    const bytes = await client.downloadOutput("out/ref");

    assert.equal(
      captured.url,
      "https://api.consentguard.test/v1/output/download/out%2Fref"
    );
    assert.equal(captured.headers?.get("X-API-Key"), TEST_API_KEY);
    assert.deepEqual([...bytes], [1, 2, 3]);
  });

  it("matches the backend consent verification request and response", async () => {
    const captured: {
      url: string;
      headers: Headers | null;
      body: Record<string, unknown>;
    } = { url: "", headers: null, body: {} };
    const mockFetch = async (
      input: RequestInfo | URL,
      init?: RequestInit
    ): Promise<Response> => {
      captured.url = String(input);
      captured.headers = new Headers(init?.headers);
      captured.body = JSON.parse(String(init?.body));
      return new Response(
        JSON.stringify({ valid: false, state: "revoked" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    };
    const client = new ConsentGuard({
      apiKey: TEST_API_KEY,
      baseUrl: "https://api.consentguard.test/",
      fetch: mockFetch as any,
    });

    const response = await client.verify({
      checkId: "c_original_check",
      consentToken: "signed-token",
      targetRef: "opaque-target",
    });

    assert.equal(captured.url, "https://api.consentguard.test/v1/generate/verify");
    assert.equal(captured.headers?.get("X-API-Key"), TEST_API_KEY);
    assert.deepEqual(captured.body, {
      check_id: "c_original_check",
      consent_token: "signed-token",
      target_ref: "opaque-target",
    });
    assert.deepEqual(response, { valid: false, state: "revoked" });
  });
});
