import { NextRequest, NextResponse } from "next/server";
import { SESSION_COOKIE } from "@/lib/authCookie";

// Gates the app on the presence of a session cookie. The cookie's validity is
// confirmed by /api/auth/me once the app loads — a stale cookie just bounces the
// user back to /welcome from there. Public routes: /welcome and /api/auth/*.
const PUBLIC_PATHS = ["/welcome"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const hasSession = Boolean(request.cookies.get(SESSION_COOKIE)?.value);
  const isPublic = PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(`${p}/`));

  if (!hasSession && !isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/welcome";
    return NextResponse.redirect(url);
  }

  if (hasSession && isPublic) {
    const url = request.nextUrl.clone();
    url.pathname = "/";
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except Next internals, API routes, and static assets.
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|assets).*)"],
};
