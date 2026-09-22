"use client";

import { useState, type ReactNode } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  confirmVariant = "destructive",
  requireText,
  requireTextLabel,
  onConfirm,
  busy = false,
  confirmDisabled = false,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: ReactNode;
  confirmLabel?: string;
  /** "destructive" for delete/danger, "default" for form submits. */
  confirmVariant?: "default" | "destructive";
  /** When set, the confirm button stays disabled until the input matches. */
  requireText?: string;
  requireTextLabel?: string;
  onConfirm: () => void;
  busy?: boolean;
  /** Extra caller-side disable condition for the confirm button. */
  confirmDisabled?: boolean;
  children?: ReactNode;
}) {
  const [typed, setTyped] = useState("");
  const blocked = requireText !== undefined && typed !== requireText;
  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) setTyped(""); onOpenChange(o); }}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && <DialogDescription>{description}</DialogDescription>}
        </DialogHeader>
        {children}
        {requireText !== undefined && (
          <Input
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={requireTextLabel ?? `Type ${requireText} to confirm`}
            autoFocus
          />
        )}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Cancel
          </Button>
          <Button variant={confirmVariant} onClick={onConfirm} disabled={blocked || busy || confirmDisabled}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
