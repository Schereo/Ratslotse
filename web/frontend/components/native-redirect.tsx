"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { isNativeApp } from "@/lib/platform";

/** In the native app the marketing landing page is dead weight: jump straight to
 *  the dashboard (the authed layout bounces to /login when logged out). Deep
 *  links still win — appUrlOpen events are retained by Capacitor and navigate
 *  after this replace. No-op in the browser. */
export function NativeRedirect() {
  const router = useRouter();
  useEffect(() => {
    if (isNativeApp()) router.replace("/dashboard");
  }, [router]);
  return null;
}
