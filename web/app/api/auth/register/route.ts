import { NextRequest, NextResponse } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { AGENT_API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/authCookie";
import { authResponseSchema } from "@/lib/schemas/auth";

// Proxies sign-up to the Python agent service, then stores the returned session
// token in an httpOnly cookie. Only the public user + estate reach the browser.
export async function POST(request: NextRequest) {
  return withSentrySpan("auth.register", async () => {
    const upstream = await fetch(`${AGENT_API_URL}/auth/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });

    const payload = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return NextResponse.json(payload, { status: upstream.status });
    }

    const { token, user, estate } = authResponseSchema.parse(payload);
    const response = NextResponse.json({ user, estate: estate ?? null });
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
    return response;
  });
}
