import { NextRequest, NextResponse } from "next/server";
import { getSessionCookie } from "better-auth/cookies";

export async function middleware(request: NextRequest) {
  const sessionCookie = getSessionCookie(request);
  const { pathname } = request.nextUrl;

  // Protected routes that require authentication
  const protectedPaths = ["/issues", "/api/protected"];
  const isProtectedPath = protectedPaths.some((path) => pathname.startsWith(path));

  // Auth routes that should redirect if already logged in
  const authPaths = ["/sign-in", "/sign-up"];
  const isAuthPath = authPaths.some((path) => pathname === path);

  // Redirect authenticated users away from auth pages
  if (sessionCookie && isAuthPath) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  // Redirect unauthenticated users to sign-in for protected routes
  if (!sessionCookie && isProtectedPath) {
    return NextResponse.redirect(new URL("/sign-in", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/issues/:path*",
    "/api/protected/:path*",
    "/sign-in",
    "/sign-up",
  ],
};
