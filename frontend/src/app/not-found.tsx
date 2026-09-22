import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gray-50 text-center">
      <p className="text-4xl font-semibold text-gray-900">404</p>
      <p className="text-sm text-text-muted">This page doesn&apos;t exist.</p>
      <Button asChild><Link href="/">Back to GenBI</Link></Button>
    </div>
  );
}
