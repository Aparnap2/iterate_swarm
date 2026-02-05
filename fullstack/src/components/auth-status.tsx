"use client";

import { use } from "react";
import { authClient } from "@/lib/auth-client";
import { Button } from "@/components/ui/button";
import Link from "next/link";

type SessionData = {
  user: {
    id: string;
    name: string | null;
    email: string;
    image: string | null;
  };
  session: {
    id: string;
    expiresAt: Date;
  };
};

export function AuthStatus() {
  const session = use(authClient.useSession() as unknown as Promise<{ data: SessionData | null }>);

  if (!session?.data) {
    return (
      <div className="flex items-center gap-4">
        <Link href="/sign-in">
          <Button variant="outline" size="sm">
            Sign In
          </Button>
        </Link>
        <Link href="/sign-up">
          <Button size="sm">Sign Up</Button>
        </Link>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-4">
      <span className="text-sm text-stone-600">
        {session.data.user.name || session.data.user.email}
      </span>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => authClient.signOut()}
      >
        Sign Out
      </Button>
    </div>
  );
}
