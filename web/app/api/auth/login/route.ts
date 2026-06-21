import { NextRequest, NextResponse } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { AGENT_API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/authCookie";
import { authResponseSchema } from "@/lib/schemas/auth";

// Proxies log-in to the Python agent service and stores the session token in an
// httpOnly cookie on success.
export async function POST(request: NextRequest) {
  return withSentrySpan("auth.login", async () => {
    const upstream = await fetch(`${AGENT_API_URL}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: await request.text(),
      cache: "no-store",
    });

    const payload = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return NextResponse.json(payload, { status: upstream.status });
    }

    const { token, user } = authResponseSchema.parse(payload);
    const response = NextResponse.json({ user });
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
    return response;
  });
}
