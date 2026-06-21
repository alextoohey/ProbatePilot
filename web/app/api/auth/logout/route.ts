import { NextRequest, NextResponse } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { AGENT_API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/authCookie";

// Invalidates the session in Redis (via the agent service) and clears the cookie.
export async function POST(request: NextRequest) {
  return withSentrySpan("auth.logout", async () => {
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (token) {
      await fetch(`${AGENT_API_URL}/auth/logout`, {
        method: "POST",
        headers: { authorization: `Bearer ${token}` },
        cache: "no-store",
      }).catch(() => undefined);
    }

    const response = NextResponse.json({ ok: true });
    response.cookies.set(SESSION_COOKIE, "", { ...sessionCookieOptions(), maxAge: 0 });
    return response;
  });
}
