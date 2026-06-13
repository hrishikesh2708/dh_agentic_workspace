"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type {
  ApprovalInterruptPayload,
  CanonicalMappingRow,
  ChannelConnectionStatus,
  MappingDestination,
  MappingReviewRow,
  SelectOption,
  UnresolvedField,
} from "@/hooks/use-headless-interrupt";
import { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";

export interface HitlApprovalCardProps {
  payload: ApprovalInterruptPayload;
  onApprove: (response: unknown) => void;
  onReject: (reason?: string) => void;
}

function InterruptHeader({ payload }: { payload: ApprovalInterruptPayload }) {
  if (!payload.title && !payload.message) return null;
  return (
    <div>
      {payload.title ? (
        <p className="text-sm font-semibold text-[var(--foreground)]">{payload.title}</p>
      ) : null}
      {payload.message ? (
        <p className="text-xs text-[var(--muted-foreground)] mt-0.5">{payload.message}</p>
      ) : null}
    </div>
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
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />

        <div className="flex flex-wrap gap-2">
          {options.map((opt) => {
            const isEnabled = opt.enabled !== false;
            const isSelected = selected === opt.id;

            return (
              <button
                key={opt.id}
                type="button"
                disabled={!isEnabled}
                onClick={() => isEnabled && setSelected(opt.id)}
                style={{ borderRadius: isSelected ? "8px" : "9999px" }}
                className={[
                  "inline-flex items-center gap-2 border px-3 py-1.5 text-sm font-medium",
                  "transition-all duration-300 ease-in-out",
                  isEnabled ? "cursor-pointer" : "cursor-not-allowed opacity-35",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:border-[var(--primary)]/40 hover:bg-[var(--secondary)]",
                ].join(" ")}
              >
                {/* Radio indicator */}
                <span className={[
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-all duration-300",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]"
                    : "border-[var(--muted-foreground)]/50 bg-transparent",
                ].join(" ")}>
                  {isSelected && (
                    <span className="h-1.5 w-1.5 rounded-full bg-white" />
                  )}
                </span>
                {opt.label}
                {!isEnabled && (
                  <span className="text-xs text-[var(--muted-foreground)] opacity-60">· soon</span>
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
          {selected
            ? `Continue with ${options.find((o) => o.id === selected)?.label ?? selected}`
            : "Select a source"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Select Salesforce object card ──────────────────────────────────────────

function SelectObjectCard({ payload, onApprove }: HitlApprovalCardProps) {
  const rawOptions = payload.options ?? [];
  const requested = payload.requested ?? "";

  // Normalise to strings, put suggested first
  const allObjects = rawOptions.map((o) => (typeof o === "string" ? o : (o as SelectOption).id));
  const suggested = allObjects.find(
    (o) => o.toLowerCase() === requested.toLowerCase(),
  ) ?? allObjects[0] ?? "";
  const rest = allObjects.filter((o) => o !== suggested);
  const objects = suggested ? [suggested, ...rest] : allObjects;

  const [selected, setSelected] = useState<string>(suggested);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />

        <div className="flex flex-wrap gap-2">
          {objects.map((obj) => {
            const isSelected = selected === obj;
            const isSuggested = obj === suggested;

            return (
              <button
                key={obj}
                type="button"
                onClick={() => setSelected(obj)}
                style={{ borderRadius: isSelected ? "8px" : "9999px" }}
                className={[
                  "inline-flex items-center gap-2 border px-3 py-1.5 text-sm font-medium",
                  "transition-all duration-300 ease-in-out cursor-pointer",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:border-[var(--primary)]/40 hover:bg-[var(--secondary)]",
                ].join(" ")}
              >
                {/* Radio indicator */}
                <span className={[
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-all duration-300",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]"
                    : "border-[var(--muted-foreground)]/50 bg-transparent",
                ].join(" ")}>
                  {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                </span>

                {obj}

                {isSuggested && (
                  <span className={[
                    "text-xs transition-colors duration-300",
                    isSelected ? "text-[var(--primary)]/70" : "text-[var(--muted-foreground)]",
                  ].join(" ")}>
                    suggested
                  </span>
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
          {selected ? `Continue with ${selected}` : "Select an object"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Mapping status dot ─────────────────────────────────────────────────────

function MappingStatusDot({ status }: { status: string }) {
  const cls =
    status === "confident"   ? "bg-green-500" :
    status === "needs_input" ? "bg-amber-500" :
    status === "missing"     ? "bg-red-500"   : "";
  if (!cls) return null;
  return <span className={`h-2.5 w-2.5 rounded-full shrink-0 inline-block ${cls}`} />;
}

// ── Platform colours ────────────────────────────────────────────────────────

const PLATFORM_COLORS: Record<string, string> = {
  meta_capi:      "#1877F2",
  google_offline: "#EA4335",
  google_dm:      "#FBBC04",
  tiktok:         "#010101",
  snapchat:       "#FFFC00",
  linkedin:       "#0A66C2",
  twitter:        "#1DA1F2",
  bing:           "#008373",
};

// ── Mapping review card (single + multi destination) ───────────────────────

const SOURCE_FIELD_SELECT_CLASS =
  "h-9 flex-1 min-w-0 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)] cursor-pointer focus:outline-none focus:ring-1 focus:ring-[var(--primary)] transition-colors";

function MappingReviewCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const destinations = (payload.destinations ?? []) as MappingDestination[];
  const rows = (payload.rows ?? []) as MappingReviewRow[];
  const sourceFields = (payload.source_fields ?? []) as string[];
  const isSingle = destinations.length <= 1;
  const dest = destinations[0];

  // Track user-overridden source fields per row index
  const [sourceOverrides, setSourceOverrides] = useState<Record<number, string>>({});

  function getSourceField(row: MappingReviewRow, i: number) {
    return sourceOverrides[i] ?? row.source_field;
  }

  const needsAction = rows.reduce((n, row) => {
    return n + Object.values(row.cells ?? {}).filter(
      (c) => c.status === "needs_input" || c.status === "missing",
    ).length;
  }, 0);

  function handleApprove() {
    const updatedRows = rows.map((row, i) => ({
      ...row,
      source_field: getSourceField(row, i),
    }));
    onApprove({ approved: true, rows: updatedRows });
  }

  // Shared source field dropdown
  function SourceDropdown({ row, index }: { row: MappingReviewRow; index: number }) {
    const value = getSourceField(row, index);
    if (sourceFields.length === 0) {
      // No options provided — read-only pill
      return (
        <div className="h-9 flex-1 flex items-center px-3 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm text-[var(--foreground)] min-w-0 truncate">
          {value}
        </div>
      );
    }
    return (
      <select
        value={value}
        onChange={(e) => setSourceOverrides((prev) => ({ ...prev, [index]: e.target.value }))}
        className={SOURCE_FIELD_SELECT_CLASS}
      >
        {!sourceFields.includes(value) && (
          <option value={value}>{value}</option>
        )}
        {sourceFields.map((f) => (
          <option key={f} value={f}>{f}</option>
        ))}
      </select>
    );
  }

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        {/* Header label */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          {payload.source_object}
          {isSingle && dest ? ` → ${dest.label}` : ""}
        </p>

        {isSingle ? (
          // ── Single destination: source dropdown → dest pill + dot ──────────
          <div className="space-y-2">
            {rows.map((row, i) => {
              const cell = dest ? row.cells[dest.id] : Object.values(row.cells)[0];
              return (
                <div key={i} className="flex items-center gap-2">
                  <SourceDropdown row={row} index={i} />
                  <span className="text-[var(--muted-foreground)] text-xs shrink-0">→</span>
                  <div className="flex-1 flex items-center h-9 px-3 rounded-lg border border-[var(--border)] bg-[var(--background)] text-sm text-[var(--foreground)] min-w-0 truncate">
                    {cell?.field ?? "—"}
                  </div>
                  <MappingStatusDot status={cell?.status ?? ""} />
                </div>
              );
            })}
          </div>
        ) : (
          // ── Multi destination: grid table with source dropdowns ────────────
          <div className="rounded-lg border border-[var(--border)] overflow-hidden">
            <div
              className="grid border-b border-[var(--border)] bg-[var(--secondary)]"
              style={{ gridTemplateColumns: `1.2fr ${destinations.map(() => "1fr").join(" ")}` }}
            >
              <div className="px-3 py-2 text-xs font-medium text-[var(--muted-foreground)]">
                {payload.source_object ?? "Source field"}
              </div>
              {destinations.map((d) => (
                <div key={d.id} className="px-3 py-2 flex items-center gap-1.5 border-l border-[var(--border)]">
                  <span
                    className="h-3.5 w-3.5 rounded-sm shrink-0"
                    style={{ backgroundColor: d.color ?? PLATFORM_COLORS[d.id] ?? "#888" }}
                  />
                  <span className="text-xs font-medium text-[var(--foreground)] truncate">{d.label}</span>
                </div>
              ))}
            </div>
            {rows.map((row, i) => (
              <div
                key={i}
                className="grid border-b border-[var(--border)] last:border-0 hover:bg-[var(--secondary)]/40 transition-colors"
                style={{ gridTemplateColumns: `1.2fr ${destinations.map(() => "1fr").join(" ")}` }}
              >
                <div className="px-3 py-2.5">
                  <SourceDropdown row={row} index={i} />
                </div>
                {destinations.map((d) => {
                  const cell = row.cells[d.id];
                  const isNotRequired = !cell || cell.status === "not_required";
                  return (
                    <div key={d.id} className="px-3 py-2.5 flex items-center gap-2 border-l border-[var(--border)]">
                      {isNotRequired ? (
                        <span className="text-xs text-[var(--muted-foreground)]/60 italic">— not required —</span>
                      ) : (
                        <>
                          <MappingStatusDot status={cell.status} />
                          <span className="text-sm text-[var(--foreground)] truncate">{cell.field ?? "—"}</span>
                        </>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        )}

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {[
            { color: "bg-green-500", label: "mapped & confident" },
            { color: "bg-amber-500", label: "needs your input" },
            { color: "bg-red-500",   label: "missing" },
          ].map(({ color, label }) => (
            <span key={label} className="flex items-center gap-1 text-[10px] font-medium tracking-wider text-[var(--muted-foreground)] uppercase">
              <span className={`h-2 w-2 rounded-full ${color}`} />
              {label}
            </span>
          ))}
          {!isSingle && (
            <span className="text-[10px] text-[var(--muted-foreground)]">
              · Shared rows map once → all destinations
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button type="button" className="flex-1" onClick={handleApprove}>
            {needsAction > 0 ? `Resolve ${needsAction} field${needsAction !== 1 ? "s" : ""}` : "Approve mapping"}
          </Button>
          <Button type="button" variant="outline" className="flex-1" onClick={() => onReject("edit_mapping")}>
            Edit mapping
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Canonical mapping card ──────────────────────────────────────────────────

function CanonicalMappingCard({ payload, onApprove }: HitlApprovalCardProps) {
  const rows = (payload.canonical_rows ?? []) as CanonicalMappingRow[];
  const infoText = payload.info_text;

  const needsInput = rows.filter(
    (r) => r.status === "needs_input" || r.status === "missing",
  ).length;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        {/* Header label */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          What Signals needs ← Your Salesforce field
        </p>

        {/* Rows */}
        <div className="space-y-2">
          {rows.map((row, i) => (
            <div
              key={i}
              className="flex items-center gap-3 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5"
            >
              <MappingStatusDot status={row.status} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--foreground)] leading-tight">
                  {row.canonical_field}
                </p>
                {row.description && (
                  <p className={`text-xs mt-0.5 leading-tight ${
                    row.status === "needs_input" || row.status === "missing"
                      ? "text-amber-600 dark:text-amber-400"
                      : "text-[var(--muted-foreground)]"
                  }`}>
                    {row.description}
                  </p>
                )}
              </div>
              <span className="text-[var(--muted-foreground)] text-xs shrink-0">←</span>
              <div className="w-44 shrink-0 flex items-center h-8 px-2.5 rounded-md border border-[var(--border)] bg-[var(--card)] text-sm text-[var(--foreground)] truncate">
                {row.source_field ?? (
                  <span className="text-[var(--muted-foreground)] italic text-xs">not mapped</span>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Info bar */}
        {infoText && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800/60 bg-blue-500/5 px-3 py-2">
            <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">{infoText}</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          {needsInput > 0 ? (
            <>
              <Button type="button" className="flex-1" onClick={() => onApprove({ approved: true })}>
                Resolve {needsInput} hint{needsInput !== 1 ? "s" : ""}
              </Button>
              <Button type="button" variant="outline" className="flex-1" onClick={() => onApprove({ approved: true, skip_hints: true })}>
                Looks good — validate
              </Button>
            </>
          ) : (
            <Button type="button" className="flex-1" onClick={() => onApprove({ approved: true })}>
              Looks good — validate
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Check & connect source card ───────────────────────────────────────────

type ConnectionStatusConfig = {
  bar: string;
  tint: string;
  primaryBtn: string;
  secondaryLabel: string;
};

const CONNECTION_STATUS: Record<string, ConnectionStatusConfig> = {
  not_connected: {
    bar:         "bg-red-500",
    tint:        "bg-red-500/[0.03]",
    primaryBtn:  "",
    secondaryLabel: "Use a different source",
  },
  expired: {
    bar:         "bg-amber-500",
    tint:        "bg-amber-500/[0.03]",
    primaryBtn:  "bg-amber-500 hover:bg-amber-600 text-white border-amber-500",
    secondaryLabel: "Use a different source",
  },
  connected: {
    bar:         "bg-green-500",
    tint:        "bg-green-500/[0.03]",
    primaryBtn:  "bg-green-600 hover:bg-green-700 text-white border-green-600",
    secondaryLabel: "Use a different source",
  },
};

function CheckConnectionCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const status = payload.connection_status ?? "not_connected";
  const cfg = CONNECTION_STATUS[status] ?? CONNECTION_STATUS.not_connected;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-3">
        {/* Info block with status-coloured left border */}
        <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden mb-3">
          <div className={`w-1 shrink-0 ${cfg.bar}`} />
          <div className={`px-4 py-3 space-y-0.5 flex-1 ${cfg.tint}`}>
            <p className="text-sm font-semibold text-[var(--foreground)]">
              {payload.source_label ?? payload.title ?? "Source"}
            </p>
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {payload.message ?? "No active connection found. I'll open the secure connect screen — your credentials stay on the existing authentication flow."}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            type="button"
            className={`flex-1 ${cfg.primaryBtn}`}
            onClick={() => onApprove({ action: "connect" })}
          >
            Connect {payload.source_label ?? "Source"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => onReject("change_source")}
          >
            {cfg.secondaryLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Select channels card (multi-select) ───────────────────────────────────

function SelectChannelsCard({ payload, onApprove }: HitlApprovalCardProps) {
  const options = (payload.options ?? []) as SelectOption[];
  const min = payload.min_select ?? 1;

  const defaultSelected = options
    .filter((o) => o.enabled !== false && o.id === payload.default_selected)
    .map((o) => o.id);

  const [selected, setSelected] = useState<Set<string>>(new Set(defaultSelected));

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const canContinue = selected.size >= min;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <InterruptHeader payload={payload} />

        <div className="flex flex-wrap gap-2">
          {options.map((opt) => {
            const isEnabled = opt.enabled !== false;
            const isSelected = selected.has(opt.id);

            return (
              <button
                key={opt.id}
                type="button"
                disabled={!isEnabled}
                onClick={() => isEnabled && toggle(opt.id)}
                style={{ borderRadius: isSelected ? "8px" : "9999px" }}
                className={[
                  "inline-flex items-center gap-2 border px-3 py-1.5 text-sm font-medium",
                  "transition-all duration-300 ease-in-out",
                  isEnabled ? "cursor-pointer" : "cursor-not-allowed opacity-35",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:border-[var(--primary)]/40 hover:bg-[var(--secondary)]",
                ].join(" ")}
              >
                {/* Checkbox indicator */}
                <span className={[
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border text-[10px]",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)] text-white"
                    : "border-[var(--muted-foreground)]/50 bg-transparent text-transparent",
                ].join(" ")}>
                  ✓
                </span>
                {opt.label}
              </button>
            );
          })}
        </div>

        {selected.size > 0 && (
          <p className="text-xs text-[var(--muted-foreground)]">
            {selected.size} selected
          </p>
        )}

        <Button
          type="button"
          disabled={!canContinue}
          onClick={() => onApprove({ selected: Array.from(selected) })}
          className="w-full"
        >
          Continue{selected.size > 0 ? ` with ${selected.size} channel${selected.size !== 1 ? "s" : ""}` : ""}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Resolve fields card ────────────────────────────────────────────────────

function ResolveFieldsCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const isResolved = payload.resolve_status === "resolved";
  const fields = (payload.unresolved_fields ?? []) as UnresolvedField[];
  const sourceFields = (payload.source_fields ?? []) as string[];
  const destinationLabel = payload.destination_label ?? "destination";

  // Track which fields are in "map a field" mode
  const [mappingField, setMappingField] = useState<string | null>(null);
  const [fieldMaps, setFieldMaps] = useState<Record<string, string>>({});

  const inlineChip = (label: string, onClick: () => void) => (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center rounded border border-[var(--border)] bg-[var(--background)] px-2 py-0.5 text-xs text-[var(--foreground)] hover:bg-[var(--secondary)] transition-colors cursor-pointer"
    >
      {label}
    </button>
  );

  // ── Resolved state ────────────────────────────────────────────────────────
  if (isResolved) {
    return (
      <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
        <CardContent className="p-3">
          <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden mb-3">
            <div className="w-1 shrink-0 bg-green-500" />
            <div className="px-4 py-3 space-y-0.5 flex-1 bg-green-500/[0.03]">
              <p className="text-sm font-semibold text-[var(--foreground)]">
                All required {destinationLabel} fields resolved
              </p>
              {payload.summary_text && (
                <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
                  {payload.summary_text}
                </p>
              )}
            </div>
          </div>
          <div className="flex gap-2">
            <Button type="button" className="flex-1" onClick={() => onApprove({ action: "confirm" })}>
              Confirm mapping
            </Button>
            <Button type="button" variant="outline" className="flex-1" onClick={() => onReject("edit")}>
              Edit a field
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  // ── Has issues state ──────────────────────────────────────────────────────
  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-3 space-y-2">
        {fields.map((f) => (
          <div key={f.field} className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
            <div className="w-1 shrink-0 bg-amber-500" />
            <div className="px-4 py-3 space-y-2 flex-1 bg-amber-500/[0.03]">
              <p className="text-sm font-semibold text-[var(--foreground)]">
                {f.field}
                <span className="ml-1.5 text-xs font-normal text-amber-600 dark:text-amber-400">
                  ({f.required ? "required" : "optional"}, unmapped)
                </span>
              </p>

              {/* Inline action chips */}
              {mappingField !== f.field ? (
                <div className="flex flex-wrap gap-2">
                  {f.suggested_constant && inlineChip(
                    `Set constant: ${f.suggested_constant}`,
                    () => onApprove({ action: "set_constant", field: f.field, value: f.suggested_constant }),
                  )}
                  {inlineChip("Map a field", () => setMappingField(f.field))}
                </div>
              ) : (
                // Inline field picker
                <div className="flex items-center gap-2">
                  <select
                    autoFocus
                    defaultValue=""
                    onChange={(e) => {
                      if (!e.target.value) return;
                      setFieldMaps((prev) => ({ ...prev, [f.field]: e.target.value }));
                      onApprove({ action: "map_field", field: f.field, source_field: e.target.value });
                    }}
                    className="flex-1 h-8 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  >
                    <option value="" disabled>Select a field…</option>
                    {sourceFields.map((sf) => (
                      <option key={sf} value={sf}>{sf}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => setMappingField(null)}
                    className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ── Check & connect channels card ─────────────────────────────────────────

const CHANNEL_AVATAR_COLORS: Record<string, string> = {
  meta:           "#1877F2",
  meta_capi:      "#1877F2",
  google:         "#EA4335",
  google_offline: "#EA4335",
  google_dm:      "#FBBC04",
  tiktok:         "#010101",
  snapchat:       "#FFFC00",
  linkedin:       "#0A66C2",
  twitter:        "#1DA1F2",
  bing:           "#008373",
};

function CheckChannelsCard({ payload, onApprove }: HitlApprovalCardProps) {
  const channels = (payload.channels ?? []) as ChannelConnectionStatus[];
  // First channel that still needs connecting
  const pendingChannel = channels.find((ch) => ch.status !== "connected");

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        {/* Section label */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Destinations for this integration
        </p>

        {/* Channel rows */}
        <div className="space-y-2">
          {channels.map((ch) => {
            const isConnected = ch.status === "connected";
            const avatarColor = CHANNEL_AVATAR_COLORS[ch.id] ?? "#6B7280";
            const initial = ch.label.charAt(0).toUpperCase();

            return (
              <div
                key={ch.id}
                className="flex items-center gap-3 rounded-xl border border-[var(--border)] bg-[var(--background)] px-4 py-3"
              >
                {/* Platform avatar */}
                <div
                  className="h-9 w-9 shrink-0 rounded-lg flex items-center justify-center text-white text-sm font-bold"
                  style={{ backgroundColor: avatarColor }}
                >
                  {initial}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-[var(--foreground)]">{ch.label}</p>
                  {ch.detail ? (
                    <p className="text-xs text-[var(--muted-foreground)] truncate">{ch.detail}</p>
                  ) : null}
                </div>

                {/* Status badge or inline Connect */}
                {isConnected ? (
                  <span className="shrink-0 rounded-full border border-green-500 px-3 py-1 text-xs font-medium text-green-600 dark:text-green-400">
                    Connected
                  </span>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    className="shrink-0"
                    onClick={() => onApprove({ action: "connect", platform_id: ch.id })}
                  >
                    Connect
                  </Button>
                )}
              </div>
            );
          })}
        </div>

        {/* Primary CTA */}
        {pendingChannel ? (
          <div className="flex gap-2">
            <Button
              type="button"
              className="flex-1"
              onClick={() => onApprove({ action: "connect", platform_id: pendingChannel.id })}
            >
              Connect {pendingChannel.label}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => onApprove({ action: "skip", platform_id: pendingChannel.id })}
            >
              Skip for now
            </Button>
          </div>
        ) : (
          <Button
            type="button"
            className="w-full bg-green-600 hover:bg-green-700 text-white"
            onClick={() => onApprove({ action: "confirm_all" })}
          >
            All connected — continue
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ── Activate confirm card ─────────────────────────────────────────────────

function ActivateConfirmCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const validation   = payload.validation   as { title: string; checks: string[] } | undefined;
  const summaryCard  = payload.summary_card as { title: string; lines: string[]  } | undefined;
  const confirmLabel   = payload.confirm_label   ?? "Activate";
  const secondaryLabel = payload.secondary_label ?? "Review matrix";

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        {/* Validation block — green left border */}
        {validation ? (
          <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
            <div className="w-1 shrink-0 bg-green-500" />
            <div className="px-4 py-3 flex-1 space-y-1 bg-green-500/[0.03]">
              <p className="text-sm font-semibold text-[var(--foreground)]">{validation.title}</p>
              {validation.checks.map((check, i) => (
                <p key={i} className="text-sm text-[var(--muted-foreground)]">{check}</p>
              ))}
            </div>
          </div>
        ) : null}

        {/* Summary card — plain border */}
        {summaryCard ? (
          <div className="rounded-md border border-[var(--border)] px-4 py-3 space-y-1">
            <p className="text-sm font-semibold text-[var(--foreground)]">{summaryCard.title}</p>
            {summaryCard.lines.map((line, i) => (
              <p key={i} className="text-sm text-[var(--muted-foreground)]">{line}</p>
            ))}
          </div>
        ) : null}

        {/* CTA */}
        <div className="flex gap-2 pt-1">
          <Button
            type="button"
            className="flex-1"
            onClick={() => onApprove({ action: "activate" })}
          >
            {confirmLabel}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => onReject("review_matrix")}
          >
            {secondaryLabel}
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
    // ── Agreed interrupt sequence ──────────────────────────────────────────
    case "select_channels":
      return <SelectChannelsCard {...cardProps} />;
    case "select_source":
      return <SelectSourceCard {...cardProps} />;
    case "check_connection":
      return <CheckConnectionCard {...cardProps} />;
    case "select_object":
      return <SelectObjectCard {...cardProps} />;
    case "check_channels":
      return <CheckChannelsCard {...cardProps} />;
    case "mapping_review":
      return <MappingReviewCard {...cardProps} />;
    case "canonical_mapping":
      return <CanonicalMappingCard {...cardProps} />;
    case "resolve_fields":
      return <ResolveFieldsCard {...cardProps} />;
    case "activate_confirm":
      return <ActivateConfirmCard {...cardProps} />;
    default:
      return null;
  }
}
