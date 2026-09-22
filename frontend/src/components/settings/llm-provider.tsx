"use client";

import { LLMProviderForm } from "@/components/llm/llm-provider-form";
import { Bot, ShieldCheck } from "lucide-react";

/**
 * "AI Provider" (BYOK) section of /settings — tenant admins configure the
 * tenant's own LLM key. The form itself is the shared LLMProviderForm in
 * "self" mode (live validate + revert-to-platform); this wrapper keeps the
 * section shell and the key-handling security note.
 */
export function LLMProviderSettings() {
  return (
    <section className="bg-white border border-gray-200 rounded-xl p-5 space-y-4">
      <h2 className="text-sm font-semibold text-gray-900 flex items-center gap-2">
        <Bot className="w-4 h-4 text-gray-400" /> AI Provider (bring your own key)
      </h2>

      <LLMProviderForm mode="self" />

      <p className="text-[11px] text-gray-400 flex items-start gap-1.5">
        <ShieldCheck className="w-3.5 h-3.5 mt-0.5 shrink-0" />
        The key is validated with a live 1-token ping, encrypted (pgcrypto) before storage,
        and never displayed again or sent to logs. A configured tenant never silently falls
        back to the platform key — a broken key surfaces as an error you can fix here.
      </p>
    </section>
  );
}
