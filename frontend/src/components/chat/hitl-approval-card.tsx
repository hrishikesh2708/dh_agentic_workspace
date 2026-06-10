"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type {
  ApprovalInterruptPayload,
  DestinationFieldOption,
  MappingField,
  MappingSummary,
  SelectOption,
} from "@/hooks/use-headless-interrupt";
import { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";

export interface HitlApprovalCardProps {
  payload: ApprovalInterruptPayload;
  onApprove: (response: unknown) => void;
  onReject: (reason?: string) => void;
}

function InterruptHeader({ payload }: { payload: ApprovalInterruptPayload }) {
  if (!payload.title && !payload.message && !payload.hint) return null;
  return (
    <div>
      {payload.title ? (
        <p className="text-sm font-semibold text-[var(--foreground)]">{payload.title}</p>
      ) : null}
      {payload.message ? (
        <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{payload.message}</p>
      ) : null}
      {payload.hint ? (
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-1">{payload.hint}</p>
      ) : null}
    </div>
  );
}

// ── Generic approval card ──────────────────────────────────────────────────

function GenericApprovalCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const [reason, setReason] = useState("");
  return (
    <Card className="border-amber-500/50 bg-amber-500/5">
      <CardContent className="p-4 space-y-4">
        <div>
          <p className="text-sm font-medium text-[var(--foreground)]">Approval required</p>
          <p className="text-sm text-[var(--muted-foreground)] mt-1">
            Review this proposed action before the agent continues.
          </p>
        </div>
        <p className="text-sm rounded-md border border-[var(--border)] bg-[var(--background)] p-3">
          {payload.proposal ?? "No proposal provided."}
        </p>
        <Input
          placeholder="Optional note (reason)"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          className="text-sm"
        />
        <div className="flex gap-2">
          <Button type="button" onClick={() => onApprove({ approved: true, reason: reason.trim() || undefined })}>
            Approve
          </Button>
          <Button type="button" variant="outline" onClick={() => onReject(reason.trim() || undefined)}>
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Select source CRM card ─────────────────────────────────────────────────

function SelectSourceCard({ payload, onApprove }: HitlApprovalCardProps) {
  const options = (payload.options ?? []) as SelectOption[];
  const enabledOptions = options.filter((o) => o.enabled !== false);
  const defaultId =
    payload.default_selected && enabledOptions.some((o) => o.id === payload.default_selected)
      ? payload.default_selected
      : enabledOptions[0]?.id ?? "";
  const [selected, setSelected] = useState<string>(defaultId);

  return (
    <Card className="border-blue-500/40 bg-blue-500/5">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />
        <div className="grid grid-cols-2 gap-2">
          {options.map((opt) => {
            const isEnabled = opt.enabled !== false;
            const isSelected = selected === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                disabled={!isEnabled}
                onClick={() => isEnabled && setSelected(opt.id)}
                className={[
                  "rounded-lg border px-4 py-3 text-left text-sm transition-colors",
                  isEnabled ? "cursor-pointer" : "cursor-not-allowed opacity-40",
                  isSelected && isEnabled
                    ? "border-blue-500 bg-blue-500/10 text-[var(--foreground)]"
                    : "border-[var(--border)] bg-[var(--background)] text-[var(--muted-foreground)] hover:border-blue-400/60",
                ].join(" ")}
              >
                <span className="font-medium">{opt.label}</span>
                {!isEnabled && (
                  <span className="block text-xs mt-0.5 text-[var(--muted-foreground)]">Coming soon</span>
                )}
              </button>
            );
          })}
        </div>
        <Button
          type="button"
          disabled={!selected}
          onClick={() => onApprove({ selected })}
          className="w-full"
        >
          Continue with {options.find((o) => o.id === selected)?.label ?? selected}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Select Salesforce object card ──────────────────────────────────────────

function SelectObjectCard({ payload, onApprove }: HitlApprovalCardProps) {
  const rawOptions = payload.options ?? [];
  const objects = rawOptions.map((o) => (typeof o === "string" ? o : (o as SelectOption).id));
  const requested = payload.requested ?? "";

  const defaultObject =
    payload.default_selected && objects.includes(payload.default_selected)
      ? payload.default_selected
      : requested && objects.includes(requested)
        ? requested
        : objects[0] ?? "";
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string>(defaultObject);

  const filtered = objects.filter((o) => o.toLowerCase().includes(search.toLowerCase()));

  return (
    <Card className="border-violet-500/40 bg-violet-500/5">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />
        <Input
          placeholder="Search objects…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="text-sm"
        />
        <div className="max-h-52 overflow-y-auto rounded-md border border-[var(--border)] divide-y divide-[var(--border)]">
          {filtered.length === 0 ? (
            <p className="px-3 py-2 text-xs text-[var(--muted-foreground)]">No matches</p>
          ) : (
            filtered.map((obj) => (
              <button
                key={obj}
                type="button"
                onClick={() => setSelected(obj)}
                className={[
                  "w-full text-left px-3 py-2 text-sm transition-colors",
                  selected === obj
                    ? "bg-violet-500/15 text-[var(--foreground)] font-medium"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--secondary)]",
                ].join(" ")}
              >
                {obj}
              </button>
            ))
          )}
        </div>
        <Button
          type="button"
          disabled={!selected}
          onClick={() => onApprove({ selected })}
          className="w-full"
        >
          Use {selected}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Select destination card ────────────────────────────────────────────────

const DESTINATION_ICONS: Record<string, string> = {
  canonical: "🗄️",
  meta_capi: "📣",
  google_dm: "📊",
};

function SelectDestinationCard({ payload, onApprove }: HitlApprovalCardProps) {
  const options = (payload.options ?? []) as SelectOption[];
  const defaultId =
    payload.default_selected && options.some((o) => o.id === payload.default_selected)
      ? payload.default_selected
      : options[0]?.id ?? "";
  const [selected, setSelected] = useState<string>(defaultId);

  return (
    <Card className="border-emerald-500/40 bg-emerald-500/5">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />
        <div className="grid grid-cols-1 gap-2">
          {options.map((opt) => {
            const icon = DESTINATION_ICONS[opt.id] ?? "📦";
            const description = opt.description ?? "";
            const isSelected = selected === opt.id;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => setSelected(opt.id)}
                className={[
                  "rounded-lg border px-4 py-3 text-left transition-colors",
                  isSelected
                    ? "border-emerald-500 bg-emerald-500/10"
                    : "border-[var(--border)] bg-[var(--background)] hover:border-emerald-400/60",
                ].join(" ")}
              >
                <div className="flex items-center gap-3">
                  <span className="text-xl">{icon}</span>
                  <div>
                    <p className="text-sm font-medium text-[var(--foreground)]">{opt.label}</p>
                    {description ? (
                      <p className="text-xs text-[var(--muted-foreground)]">{description}</p>
                    ) : null}
                  </div>
                  {isSelected && (
                    <span className="ml-auto text-emerald-600 dark:text-emerald-400 text-xs font-medium">✓ Selected</span>
                  )}
                </div>
              </button>
            );
          })}
        </div>
        <Button
          type="button"
          disabled={!selected}
          onClick={() => onApprove({ selected })}
          className="w-full"
        >
          Continue
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Confidence badge ───────────────────────────────────────────────────────

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    pct >= 90
      ? "bg-green-500/15 text-green-700 dark:text-green-400"
      : pct >= 50
      ? "bg-amber-500/15 text-amber-700 dark:text-amber-400"
      : "bg-red-500/15 text-red-700 dark:text-red-400";
  return (
    <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${color}`}>
      {pct}%
    </span>
  );
}

// ── Mapping review card ────────────────────────────────────────────────────

type RowOverride = { destination_field: string; status: "human_approved" | "human_corrected" };

const SELECT_CLASS =
  "h-7 w-full min-w-[10rem] rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-blue-500";

function buildDestinationOptions(
  schemaFields: DestinationFieldOption[],
  mappings: MappingField[],
): DestinationFieldOption[] {
  const byName = new Map(schemaFields.map((f) => [f.name, f]));
  for (const m of mappings) {
    const suggested = m.destination_field?.trim();
    if (suggested && !byName.has(suggested)) {
      byName.set(suggested, { name: suggested, label: suggested });
    }
  }
  return Array.from(byName.values());
}

function formatMappingStatus(status?: string): string {
  if (status === "not_proposed") return "Not mapped";
  return status?.replace(/_/g, " ") ?? "";
}

function computeMappingSummary(mappings: MappingField[]): MappingSummary {
  return {
    total_source_fields: mappings.length,
    mapped: mappings.filter((m) => m.destination_field?.trim()).length,
    not_proposed: mappings.filter((m) => m.status === "not_proposed").length,
    needs_review: mappings.filter(
      (m) => m.status === "needs_review" || m.status === "unmatched",
    ).length,
  };
}

function MappingReviewCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const mappings: MappingField[] = payload.mappings ?? [];
  const destOptions = buildDestinationOptions(payload.destination_fields ?? [], mappings);
  const hasSchemaOptions = (payload.destination_fields ?? []).length > 0;
  const [overrides, setOverrides] = useState<Record<string, RowOverride>>({});
  const [globalReason, setGlobalReason] = useState("");

  const summary = payload.mapping_summary ?? computeMappingSummary(mappings);
  const needsReview = mappings.filter(
    (m) => m.status === "needs_review" || m.status === "unmatched",
  );

  function setDest(sourceField: string, dest: string) {
    setOverrides((prev) => ({
      ...prev,
      [sourceField]: {
        destination_field: dest,
        status:
          dest !== (mappings.find((m) => m.source_field === sourceField)?.destination_field ?? "")
            ? "human_corrected"
            : "human_approved",
      },
    }));
  }

  function shouldIncludeInReview(m: MappingField): boolean {
    const ov = overrides[m.source_field];
    if (m.status === "needs_review" || m.status === "unmatched") return true;
    if (!ov) return false;
    if (m.status === "not_proposed") {
      return (ov.destination_field?.trim() ?? "") !== "";
    }
    return true;
  }

  function handleApproveAll() {
    const reviews = mappings
      .filter(shouldIncludeInReview)
      .map((m) => ({
        source_field: m.source_field,
        destination_field:
          overrides[m.source_field]?.destination_field ?? m.destination_field ?? "",
        status: overrides[m.source_field]?.status ?? "human_approved",
      }));
    onApprove({ approved: true, reviews, reason: globalReason.trim() || undefined });
  }

  return (
    <Card className="border-blue-500/40 bg-blue-500/5 w-full">
      <CardContent className="p-4 space-y-4">
        <div>
          <p className="text-sm font-semibold text-[var(--foreground)]">Field mapping review</p>
          <p className="text-xs text-[var(--muted-foreground)] mt-0.5">
            <span className="font-medium">{payload.source_object}</span>
            {" → "}
            <span className="font-medium">{payload.destination_type}</span>
            {" · "}
            {payload.mapping_kind === "canonical" ? "Stage 1: canonical" : "Stage 2: projection"}
          </p>
          <p className="text-xs text-[var(--muted-foreground)] mt-1">
            {summary.total_source_fields} source fields · {summary.mapped} mapped ·{" "}
            {summary.not_proposed} not mapped by agent
            {summary.needs_review > 0 && ` · ${summary.needs_review} need review`}
          </p>
        </div>

        <div className="rounded-md border border-[var(--border)] text-xs overflow-hidden">
          <div
            className="max-h-[50vh] overflow-y-auto overflow-x-auto overscroll-contain [scrollbar-gutter:stable]"
            role="region"
            aria-label="Field mappings table"
          >
            <table className="w-full min-w-[32rem] table-fixed">
              <thead className="sticky top-0 z-10">
                <tr className="bg-[var(--secondary)] border-b border-[var(--border)] shadow-[0_1px_0_0_var(--border)]">
                  <th className="w-[22%] text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Source field</th>
                  <th className="w-[38%] text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Destination field</th>
                  <th className="w-[18%] text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Confidence</th>
                  <th className="w-[22%] text-left px-3 py-2 font-medium text-[var(--muted-foreground)]">Status</th>
                </tr>
              </thead>
              <tbody>
                {mappings.map((m) => {
                  const ov = overrides[m.source_field];
                  const currentDest = ov?.destination_field ?? m.destination_field ?? "";
                  return (
                    <tr
                      key={m.source_field}
                      className="border-b border-[var(--border)] last:border-0 hover:bg-[var(--secondary)]/50"
                    >
                      <td className="px-3 py-2 font-mono text-[var(--foreground)] truncate" title={m.source_field}>
                        {m.source_field}
                      </td>
                      <td className="px-3 py-2 max-w-0">
                      {hasSchemaOptions ? (
                        <select
                          value={currentDest}
                          onChange={(e) => setDest(m.source_field, e.target.value)}
                          className={SELECT_CLASS}
                        >
                          <option value="">Select destination field</option>
                          {destOptions.map((f) => (
                            <option key={f.name} value={f.name}>
                              {f.label ?? f.name}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <Input
                          value={currentDest}
                          onChange={(e) => setDest(m.source_field, e.target.value)}
                          placeholder="Enter destination field…"
                          className="h-6 text-xs py-0 px-2"
                        />
                      )}
                    </td>
                    <td className="px-3 py-2 whitespace-nowrap">
                      <ConfidenceBadge value={m.confidence} />
                    </td>
                    <td className="px-3 py-2 text-[var(--muted-foreground)] whitespace-nowrap">
                      {formatMappingStatus(m.status)}
                    </td>
                  </tr>
                );
              })}
              </tbody>
            </table>
          </div>
        </div>

        <p className="text-xs text-amber-600 dark:text-amber-400">
          All {summary.total_source_fields} source fields are listed. Change any destination via the
          {hasSchemaOptions ? " dropdown" : " input"} to map it.
          {needsReview.length > 0 && (
            <>
              {" "}
              {needsReview.length} field{needsReview.length !== 1 ? "s" : ""} need review — leave unmapped
              fields empty if you do not want them stored.
            </>
          )}
        </p>

        <Input
          placeholder="Optional note…"
          value={globalReason}
          onChange={(e) => setGlobalReason(e.target.value)}
          className="text-sm"
        />

        <div className="flex gap-2">
          <Button type="button" onClick={handleApproveAll}>
            Approve all
          </Button>
          <Button type="button" variant="outline" onClick={() => onReject(globalReason.trim() || undefined)}>
            Reject
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Public component — routes to correct variant ───────────────────────────

export function HitlApprovalCard(props: HitlApprovalCardProps) {
  const payload = normalizeInterruptPayload(props.payload);
  const cardProps = { ...props, payload };

  switch (payload.type) {
    case "select_source":
      return <SelectSourceCard {...cardProps} />;
    case "select_object":
      return <SelectObjectCard {...cardProps} />;
    case "select_destination":
      return <SelectDestinationCard {...cardProps} />;
    case "mapping_review":
      return <MappingReviewCard {...cardProps} />;
    default:
      return <GenericApprovalCard {...cardProps} />;
  }
}
