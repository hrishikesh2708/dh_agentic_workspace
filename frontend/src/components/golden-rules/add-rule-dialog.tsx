"use client";

import { useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import type { GoldenRuleCreate, GoldenRuleRead } from "@/lib/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";

interface AddRuleDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function AddRuleDialog({
  open,
  onOpenChange,
  onCreated,
}: AddRuleDialogProps) {
  const [sourcePattern, setSourcePattern] = useState("");
  const [destinationField, setDestinationField] = useState("");
  const [destinationType, setDestinationType] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setSourcePattern("");
    setDestinationField("");
    setDestinationType("");
    setError(null);
  }

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const body: GoldenRuleCreate = {
        source_pattern: sourcePattern,
        destination_field: destinationField,
        destination_type: destinationType,
      };
      await apiClient.post<GoldenRuleRead>("/golden-rules", body);
      reset();
      onOpenChange(false);
      onCreated();
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("create_failed");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value) reset();
        onOpenChange(value);
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add golden rule</DialogTitle>
          <DialogDescription>
            Manually record a source-to-destination mapping. Source pattern is
            lowercased automatically.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={onSubmit} className="space-y-4">
          {error ? (
            <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
              {error}
            </div>
          ) : null}
          <div className="space-y-2">
            <Label htmlFor="source_pattern">Source pattern</Label>
            <Input
              id="source_pattern"
              required
              value={sourcePattern}
              onChange={(e) => setSourcePattern(e.target.value)}
              placeholder="lead_email"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="destination_field">Destination field</Label>
            <Input
              id="destination_field"
              required
              value={destinationField}
              onChange={(e) => setDestinationField(e.target.value)}
              placeholder="email"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="destination_type">Destination type</Label>
            <Input
              id="destination_type"
              required
              value={destinationType}
              onChange={(e) => setDestinationType(e.target.value)}
              placeholder="canonical_contact"
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? <Spinner size="sm" /> : null}
              {submitting ? "Saving..." : "Save rule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
