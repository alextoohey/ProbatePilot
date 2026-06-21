import { NextRequest } from "next/server";
import { withSentrySpan } from "@/lib/sentry";
import { SESSION_COOKIE } from "@/lib/authCookie";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://localhost:8000";

async function proxy(request: NextRequest, { params }: { params: { path: string[] } }) {
  return withSentrySpan("agent.proxy", async () => {
    const url = `${AGENT_API_URL}/${params.path.join("/")}${request.nextUrl.search}`;
    const method = request.method;
    const body = method === "GET" || method === "HEAD" ? undefined : await request.arrayBuffer();
    const headers = new Headers(request.headers);
    headers.delete("host");
    headers.delete("content-length");
    const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
    if (sessionToken) headers.set("authorization", `Bearer ${sessionToken}`);

    const response = await fetch(url, {
      method,
      headers,
      body,
      // Next's fetch cache does not apply to this proxy; keep agent calls live.
      cache: "no-store",
    });

    return new Response(response.body, {
      status: response.status,
      headers: response.headers,
    });
  });
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const DELETE = proxy;
