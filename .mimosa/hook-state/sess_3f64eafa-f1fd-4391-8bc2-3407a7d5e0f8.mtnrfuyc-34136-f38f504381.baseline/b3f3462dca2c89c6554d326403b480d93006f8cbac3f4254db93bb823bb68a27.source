"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { LoginForm } from "@/components/auth/login-form";
import { useAuth } from "@/components/auth/auth-provider";

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
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-50">
        <div className="w-3 h-3 bg-brand-600 rounded-full animate-bounce" />
      </div>
    );
  }

  return <LoginForm onSuccess={() => router.replace("/chat")} />;
}
