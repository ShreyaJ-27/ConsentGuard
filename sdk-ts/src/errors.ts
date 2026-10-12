/**
 * Base error class for all ConsentGuard SDK errors.
 */
export class ConsentGuardError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConsentGuardError";
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Error raised when the ConsentGuard gateway returns a non-2xx HTTP status.
 */
export class ConsentGuardApiError extends ConsentGuardError {
  public readonly statusCode: number;
  public readonly errorCode: string;
  public readonly details?: unknown;

  constructor(statusCode: number, errorCode: string, message: string, details?: unknown) {
    super(message);
    this.name = "ConsentGuardApiError";
    this.statusCode = statusCode;
    this.errorCode = errorCode;
    this.details = details;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Error raised when network connectivity fails.
 */
export class ConsentGuardNetworkError extends ConsentGuardError {
  public readonly cause?: unknown;

  constructor(message: string, cause?: unknown) {
    super(message);
    this.name = "ConsentGuardNetworkError";
    this.cause = cause;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Error raised when a request exceeds the configured timeout.
 */
export class ConsentGuardTimeoutError extends ConsentGuardError {
  public readonly timeoutMs: number;

  constructor(timeoutMs: number) {
    super(`Request timed out after ${timeoutMs}ms`);
    this.name = "ConsentGuardTimeoutError";
    this.timeoutMs = timeoutMs;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/**
 * Redacts any occurrence of sensitive strings (such as API keys) from error text.
 */
export function sanitizeErrorMessage(text: string, apiKey?: string): string {
  if (!apiKey) {
    return text;
  }
  return text.split(apiKey).join("[REDACTED_API_KEY]");
}
