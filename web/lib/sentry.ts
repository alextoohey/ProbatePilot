import * as Sentry from "@sentry/nextjs";

/**
 * Wrap a server-side action (proxy/voice route handlers) in a Sentry span so
 * every agent interaction and voice call is observable. Errors are captured
 * and re-thrown so the route still returns its normal error response.
 */
export async function withSentrySpan<T>(name: string, action: () => Promise<T>): Promise<T> {
  return Sentry.startSpan({ name, op: "http.server" }, async () => {
    try {
      return await action();
    } catch (error) {
      Sentry.captureException(error);
      throw error;
    }
  });
}
