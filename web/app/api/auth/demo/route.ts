import { NextResponse } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { AGENT_API_URL, SESSION_COOKIE, sessionCookieOptions } from "@/lib/authCookie";
import { authResponseSchema } from "@/lib/schemas/auth";

// Signs the visitor into the shared demo account (seeded Robert Milligan
// estate) with no registration step, for the "Try the demo" entry point on
// the welcome page. Same cookie flow as /api/auth/login.
export async function POST() {
  return withSentrySpan("auth.demo", async () => {
    const upstream = await fetch(`${AGENT_API_URL}/auth/demo`, {
      method: "POST",
      cache: "no-store",
    });

    const payload = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return NextResponse.json(payload, { status: upstream.status });
    }

    const { token, user, estate } = authResponseSchema.parse(payload);
    const response = NextResponse.json({ user, estate });
    response.cookies.set(SESSION_COOKIE, token, sessionCookieOptions());
    return response;
  });
}
