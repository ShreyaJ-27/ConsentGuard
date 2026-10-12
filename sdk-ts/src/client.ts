import {
  ConsentGuardApiError,
  ConsentGuardError,
  ConsentGuardNetworkError,
  ConsentGuardTimeoutError,
  sanitizeErrorMessage,
} from "./errors";
import {
  CheckRequest,
  CheckResponse,
  ConsentGuardConfig,
  LookupResponse,
  StampReceipt,
  StampRequest,
  VerifyConsentRequest,
  VerifyConsentResponse,
} from "./types";

function isAbortError(error: unknown): boolean {
  return (
    error !== null &&
    typeof error === "object" &&
    (error as { name?: unknown }).name === "AbortError"
  );
}

/**
 * Official TypeScript client for the ConsentGuard safety gateway.
 */
export class ConsentGuard {
  private readonly apiKey: string;
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchFn: typeof fetch;

  constructor(config: ConsentGuardConfig) {
    if (!config || !config.apiKey || typeof config.apiKey !== "string" || !config.apiKey.trim()) {
      throw new ConsentGuardError("A non-empty apiKey is required to initialize ConsentGuard client.");
    }
    this.apiKey = config.apiKey.trim();
    this.baseUrl = (config.baseUrl || "http://127.0.0.1:8000").replace(/\/+$/, "");
    this.timeoutMs = config.timeoutMs ?? 10000;
    this.fetchFn = config.fetch || globalThis.fetch;

    if (!Number.isFinite(this.timeoutMs) || this.timeoutMs <= 0) {
      throw new ConsentGuardError("timeoutMs must be a positive finite number.");
    }
    if (typeof this.fetchFn !== "function") {
      throw new ConsentGuardError(
        "No global fetch found and no custom fetch provided. Please provide a fetch implementation in config."
      );
    }
  }

  /**
   * Request check: evaluate prompt risk, structured scope, and consent requirements.
   */
  public async check(request: CheckRequest): Promise<CheckResponse> {
    const payload = {
      prompt: request.prompt,
      scope: request.scope,
      user_ref: request.userRef,
      consent_token: request.consentToken ?? null,
      consent_check_id: request.consentCheckId ?? null,
      target_ref: request.targetRef ?? null,
      test_signals: request.testSignals
        ? {
            real_face: request.testSignals.real_face,
            minor_risk: request.testSignals.minor_risk,
          }
        : undefined,
    };

    const data = await this.requestJson<any>("/v1/check", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    return {
      checkId: data.check_id,
      decision: data.decision,
      tier: data.tier,
      reasons: data.reasons,
      consentRequired: Boolean(data.consent_required),
      requestRisk: {
        score: data.request_risk.score,
        label: data.request_risk.label,
        source: data.request_risk.source,
      },
    };
  }

  /**
   * Output stamp: execute defensive result checks, add visible AI label,
   * append hash-chained ledger entry, and return a verified provenance receipt.
   */
  public async stamp(request: StampRequest): Promise<StampReceipt> {
    const formData = new FormData();
    formData.append("check_id", request.checkId);

    let blob: Blob;
    if (typeof Blob !== "undefined" && request.image instanceof Blob) {
      blob = request.image;
    } else if (request.image instanceof ArrayBuffer) {
      blob = new Blob([request.image], { type: "image/png" });
    } else if (ArrayBuffer.isView(request.image)) {
      const uint8 = new Uint8Array(
        request.image.buffer,
        request.image.byteOffset,
        request.image.byteLength
      );
      blob = new Blob([uint8 as any], { type: "image/png" });
    } else {
      throw new ConsentGuardError("Unsupported image payload type. Expected Blob, Buffer, or Uint8Array.");
    }

    formData.append("image", blob, request.filename || "output.png");

    if (request.mockSignal) {
      formData.append("mock_signal", request.mockSignal);
    }
    if (request.consentToken) {
      formData.append("consent_token", request.consentToken);
    }
    if (request.targetRef) {
      formData.append("target_ref", request.targetRef);
    }

    const data = await this.requestJson<any>("/v1/output/stamp", {
      method: "POST",
      body: formData,
    });

    return {
      checkId: data.check_id,
      entryId: data.entry_id,
      outputSha256: data.output_sha256,
      preStampSha256: data.pre_stamp_sha256,
      phash: data.phash,
      label: data.label,
      createdAt: data.created_at,
      ledgerEntryHash: data.ledger_entry_hash,
      outputRef: data.output_ref,
    };
  }

  /**
   * Download the stamped image bytes using a short-lived output reference.
   */
  public async downloadOutput(outputRef: string): Promise<Uint8Array> {
    return this.executeRequest(
      `/v1/output/download/${encodeURIComponent(outputRef)}`,
      { method: "GET" },
      async (response) => new Uint8Array(await response.arrayBuffer())
    );
  }

  /**
   * Origin lookup: query the provenance ledger by perceptual hash.
   */
  public async lookup(phash: string, maxDistance: number = 0): Promise<LookupResponse> {
    const query = new URLSearchParams({
      phash: phash.trim(),
      max_distance: String(maxDistance),
    });

    const data = await this.requestJson<any>(`/v1/ledger/lookup?${query.toString()}`, {
      method: "GET",
    });

    return {
      match: Boolean(data.match),
      method: data.method,
      provenance: data.provenance
        ? {
            checkId: data.provenance.check_id,
            label: data.provenance.label,
            createdAt: data.provenance.created_at,
            outputSha256: data.provenance.output_sha256,
          }
        : null,
      message: data.message ?? null,
      distance: data.distance ?? null,
    };
  }

  /** Verify a consent grant against its check, scope, application, and target. */
  public async verify(request: VerifyConsentRequest): Promise<VerifyConsentResponse> {
    const data = await this.requestJson<any>("/v1/generate/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        check_id: request.checkId,
        consent_token: request.consentToken,
        target_ref: request.targetRef,
      }),
    });

    return {
      valid: Boolean(data.valid),
      state: data.state,
    };
  }

  private async requestJson<T>(path: string, options: RequestInit): Promise<T> {
    return this.executeRequest(path, options, async (response) => {
      try {
        return (await response.json()) as T;
      } catch (err: unknown) {
        if (isAbortError(err)) {
          throw err;
        }
        throw new ConsentGuardError("Gateway returned malformed JSON response.");
      }
    });
  }

  private async executeRequest<T>(
    path: string,
    options: RequestInit,
    readResponse: (response: Response) => Promise<T>
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeoutMs);

    const headers = new Headers(options.headers || {});
    headers.set("X-API-Key", this.apiKey);

    try {
      const response = await this.fetchFn(url, {
        ...options,
        headers,
        signal: controller.signal,
      });

      if (!response.ok) {
        let errorCode = `http_${response.status}`;
        let errorMessage = `HTTP ${response.status} ${response.statusText}`;
        let errorDetails: unknown = undefined;

        try {
          const body = await response.json();
          if (body && typeof body === "object" && body.error) {
            if (typeof body.error.code === "string") {
              errorCode = body.error.code;
            }
            if (typeof body.error.message === "string") {
              errorMessage = body.error.message;
            }
          }
        } catch (err: unknown) {
          if (isAbortError(err)) {
            throw err;
          }
          // If body is not JSON, use default statusText
        }

        const sanitizedCode = sanitizeErrorMessage(errorCode, this.apiKey);
        const sanitizedMessage = sanitizeErrorMessage(errorMessage, this.apiKey);
        errorDetails = { code: sanitizedCode, message: sanitizedMessage };
        throw new ConsentGuardApiError(
          response.status,
          sanitizedCode,
          sanitizedMessage,
          errorDetails
        );
      }

      return await readResponse(response);
    } catch (err: unknown) {
      if (err instanceof ConsentGuardError) {
        throw err;
      }
      if (isAbortError(err)) {
        throw new ConsentGuardTimeoutError(this.timeoutMs);
      }
      const rawMessage = err instanceof Error ? err.message : String(err);
      const sanitized = sanitizeErrorMessage(rawMessage, this.apiKey);
      throw new ConsentGuardNetworkError(`Network request failed: ${sanitized}`);
    } finally {
      clearTimeout(timeoutId);
    }
  }
}
