import { NextRequest, NextResponse } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { AGENT_API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/authCookie";
import { meResponseSchema } from "@/lib/schemas/auth";

// Returns the logged-in user and their estates. Forwards the session cookie to
// the agent service as a Bearer token; a stale cookie is cleared.
export async function GET(request: NextRequest) {
  return withSentrySpan("auth.me", async () => {
    const token = request.cookies.get(SESSION_COOKIE)?.value;
    if (!token) {
      return NextResponse.json({ error: "Not authenticated" }, { status: 401 });
    }

    const upstream = await fetch(`${AGENT_API_URL}/auth/me`, {
      method: "GET",
      headers: { authorization: `Bearer ${token}` },
      cache: "no-store",
    });

    if (upstream.status === 401) {
      const response = NextResponse.json({ error: "Not authenticated" }, { status: 401 });
      response.cookies.set(SESSION_COOKIE, "", { ...sessionCookieOptions(), maxAge: 0 });
      return response;
    }

    const payload = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return NextResponse.json(payload, { status: upstream.status });
    }
    return NextResponse.json(meResponseSchema.parse(payload));
  });
}
