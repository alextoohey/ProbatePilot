// Shared server-side auth constants. The session token issued by the Python
// agent service is stored in this httpOnly cookie; the browser never sees it.

export const SESSION_COOKIE = "executor_session";
export const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://localhost:8000";
export const SESSION_MAX_AGE = 60 * 60 * 24 * 30; // 30 days, matches the agent TTL

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  };
}
