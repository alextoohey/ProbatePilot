"use client";

import { useRouter } from "next/navigation";
import { AuthLanding } from "@/components/screens/AuthLanding";

// Marketing landing + log in + sign-up wizard. On log in or finished sign-up,
// the executor lands in the app (the AppShell at "/").
export default function WelcomePage() {
  const router = useRouter();
  return <AuthLanding onEnterApp={() => router.push("/")} />;
}
