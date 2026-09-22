"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/components/auth/login-form";
import { useAuth } from "@/components/auth/auth-provider";
import { Loader } from "@/components/ui/loader";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, loading } = useAuth();

  // Already signed in — send them straight to the chat.
  useEffect(() => {
    if (!loading && isAuthenticated) {
      router.replace("/chat");
    }
  }, [loading, isAuthenticated, router]);

  if (loading) {
    return <Loader fullScreen />;
  }

  return <LoginForm onSuccess={() => router.replace("/chat")} />;
}
