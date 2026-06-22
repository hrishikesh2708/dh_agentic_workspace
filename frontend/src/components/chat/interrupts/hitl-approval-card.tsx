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

// ── Select source CRM card ─────────────────────────────────────────────────

function SelectSourceCard({ payload, onApprove }: HitlApprovalCardProps) {
  const options = (payload.options ?? []) as SelectOption[];
  const enabledOptions = options.filter((o) => o.enabled !== false);

  // Backend sends recommended (= the LLM-inferred or already-valid source id)
  const recommended = (payload.recommended as string | undefined) || "";

  // Normalize default_selected — may be string | string[]
  const rawDefault = Array.isArray(payload.default_selected)
    ? payload.default_selected[0]
    : payload.default_selected;
  const defaultId =
    rawDefault && enabledOptions.some((o) => o.id === rawDefault)
      ? rawDefault
      : enabledOptions[0]?.id ?? "";

  const [selected, setSelected] = useState<string>(defaultId);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        {/* Section label — message/hint rendered as chat bubbles in headless-chat */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          {(payload.title as string | undefined) || "Data source"}
        </p>

        <div className="flex flex-wrap gap-2">
          {options.map((opt) => {
            const isEnabled = opt.enabled !== false;
            const isSelected = selected === opt.id;
            const isSuggested = !!recommended && opt.id === recommended;

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
                {isSuggested && (
                  <span className={[
                    "text-[10px] font-medium transition-colors duration-300",
                    isSelected ? "text-[var(--primary)]/70" : "text-[var(--muted-foreground)]",
                  ].join(" ")}>
                    suggested
                  </span>
                )}
                {!isEnabled && (
                  <span className="text-[10px] text-[var(--muted-foreground)] opacity-70">soon</span>
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

  // Backend sends recommended (and default_selected = recommended).
  // payload.requested is not used for the normal gather_object flow.
  const recommended =
    (payload.recommended as string | undefined) ||
    (Array.isArray(payload.default_selected)
      ? payload.default_selected[0]
      : payload.default_selected) ||
    "";

  // Normalise options to strings — backend may send string[] or SelectOption[]
  const allObjects = rawOptions.map((o) => (typeof o === "string" ? o : (o as SelectOption).id));

  // Backend already orders: recommended first, alternatives next, then rest.
  // If recommended isn't first, move it there so the UI matches the PRD.
  const suggested = recommended
    ? (allObjects.find((o) => o.toLowerCase() === recommended.toLowerCase()) ?? "")
    : allObjects[0] ?? "";
  const rest = allObjects.filter((o) => o !== suggested);
  const objects = suggested ? [suggested, ...rest] : allObjects;

  const [selected, setSelected] = useState<string>(suggested || allObjects[0] || "");

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        {/* Section label — message/hint rendered as chat bubbles in headless-chat */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          {(payload.title as string | undefined) || "Salesforce object"}
        </p>

        <div className="flex flex-wrap gap-2">
          {objects.map((obj) => {
            const isSelected = selected === obj;
            // Show "suggested" badge on the backend-recommended option
            const isSuggested = obj === suggested && !!recommended;

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
                    "text-[10px] font-medium transition-colors duration-300",
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
  const sourceFields = (payload.source_fields ?? []) as string[];
  const infoText = payload.info_text;

  // Track user overrides: canonical_field → chosen source_field
  const [overrides, setOverrides] = useState<Record<string, string>>(() =>
    Object.fromEntries(rows.map((r) => [r.canonical_field, r.source_field ?? ""])),
  );

  const hasUnresolved = rows.some(
    (r) => r.status === "needs_input" || r.status === "missing",
  );

  function handleApprove() {
    const updatedRows = rows.map((r) => ({
      ...r,
      source_field: overrides[r.canonical_field] ?? r.source_field,
    }));
    onApprove({ approved: true, rows: updatedRows });
  }

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        {/* Header label */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          What Signals needs ← Your Salesforce field
        </p>

        {/* Rows */}
        <div className="space-y-2">
          {rows.map((row) => {
            const currentValue = overrides[row.canonical_field] ?? "";
            return (
              <div
                key={row.canonical_field}
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

                {/* Source field — dropdown if options provided, read-only pill otherwise */}
                {sourceFields.length > 0 ? (
                  <select
                    value={currentValue}
                    onChange={(e) =>
                      setOverrides((prev) => ({ ...prev, [row.canonical_field]: e.target.value }))
                    }
                    className="w-44 shrink-0 h-8 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] cursor-pointer"
                  >
                    {!sourceFields.includes(currentValue) && currentValue && (
                      <option value={currentValue}>{currentValue}</option>
                    )}
                    {!currentValue && (
                      <option value="" disabled>Select field…</option>
                    )}
                    {sourceFields.map((f) => (
                      <option key={f} value={f}>{f}</option>
                    ))}
                  </select>
                ) : (
                  <div className="w-44 shrink-0 flex items-center h-8 px-2.5 rounded-md border border-[var(--border)] bg-[var(--card)] text-sm text-[var(--foreground)] truncate">
                    {currentValue || (
                      <span className="text-[var(--muted-foreground)] italic text-xs">not mapped</span>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Info bar */}
        {infoText && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800/60 bg-blue-500/5 px-3 py-2">
            <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">{infoText}</p>
          </div>
        )}

        {/* Single CTA */}
        <Button
          type="button"
          className="w-full"
          onClick={handleApprove}
        >
          {hasUnresolved ? "Continue" : "Looks good — continue"}
        </Button>
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
  const isConnected = status === "connected";
  const sourceLabel = payload.source_label ?? "Source";

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-3">
        {/* Info block with status-coloured left border */}
        <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden mb-3">
          <div className={`w-1 shrink-0 ${cfg.bar}`} />
          <div className={`px-4 py-3 space-y-0.5 flex-1 ${cfg.tint}`}>
            <p className="text-sm font-semibold text-[var(--foreground)]">
              {sourceLabel}
            </p>
            {payload.account_detail && (
              <p className="text-xs font-medium text-[var(--muted-foreground)]">
                {payload.account_detail}
              </p>
            )}
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {payload.message}
            </p>
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            type="button"
            className={`flex-1 ${cfg.primaryBtn}`}
            onClick={() => onApprove({ action: isConnected ? "confirm" : "connect" })}
          >
            {isConnected ? "Continue" : `Connect ${sourceLabel}`}
          </Button>
          {/* Secondary only shown when not already connected */}
          {!isConnected && (
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              onClick={() => onReject("change_source")}
            >
              {cfg.secondaryLabel}
            </Button>
          )}
        </div>



      </CardContent>
    </Card>
  );
}

// ── Select channels card (multi-select) ───────────────────────────────────

function SelectChannelsCard({ payload, onApprove }: HitlApprovalCardProps) {
  const options = (payload.options ?? []) as SelectOption[];
  const min = payload.min_select ?? 1;

  // default_selected can be a string or string[]
  const defaultIds = Array.isArray(payload.default_selected)
    ? payload.default_selected
    : payload.default_selected
    ? [payload.default_selected]
    : [];
  const validDefaultIds = defaultIds.filter((id) =>
    options.some((o) => o.id === id && o.enabled !== false),
  );

  const [selected, setSelected] = useState<Set<string>>(new Set(validDefaultIds));

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  const canContinue = selected.size >= min;
  const selectedLabels = options
    .filter((o) => selected.has(o.id))
    .map((o) => o.label)
    .join(", ");

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        {/* Section label — message/hint rendered as chat bubbles in headless-chat */}
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          {(payload.title as string | undefined) || "Ad platforms"}
        </p>

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
                {!isEnabled && (
                  <span className="text-[10px] text-[var(--muted-foreground)] opacity-70">soon</span>
                )}
              </button>
            );
          })}
        </div>

        {selected.size > 0 && (
          <p className="text-xs text-[var(--muted-foreground)] truncate">
            {selectedLabels}
          </p>
        )}

        <Button
          type="button"
          disabled={!canContinue}
          onClick={() => onApprove({ selected: Array.from(selected) })}
          className="w-full"
        >
          {canContinue
            ? `Continue with ${selected.size} channel${selected.size !== 1 ? "s" : ""}`
            : `Select at least ${min} channel${min !== 1 ? "s" : ""}`}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Resolve fields card ────────────────────────────────────────────────────

type FieldResolution =
  | { type: "constant"; value: string }
  | { type: "field"; source_field: string };

function ResolveFieldsCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const isResolved = payload.resolve_status === "resolved";
  const fields = (payload.unresolved_fields ?? []) as UnresolvedField[];
  const sourceFields = (payload.source_fields ?? []) as string[];
  const destinationLabel = payload.destination_label ?? "destination";

  // Per-field resolution state — null = still pending
  const [resolutions, setResolutions] = useState<Record<string, FieldResolution | null>>({});
  // Which field currently has the inline dropdown open
  const [mappingField, setMappingField] = useState<string | null>(null);

  function resolve(field: string, resolution: FieldResolution) {
    setResolutions((prev) => ({ ...prev, [field]: resolution }));
    setMappingField(null);
  }

  function clearResolution(field: string) {
    setResolutions((prev) => ({ ...prev, [field]: null }));
  }

  function handleSubmit() {
    const resolvedList = fields
      .map((f) => {
        const r = resolutions[f.field];
        if (!r) return null;
        return r.type === "constant"
          ? { field: f.field, action: "set_constant", value: r.value }
          : { field: f.field, action: "map_field", source_field: r.source_field };
      })
      .filter(Boolean);
    onApprove({ action: "submit", resolutions: resolvedList });
  }

  const resolvedCount = fields.filter((f) => resolutions[f.field]).length;

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
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase mb-3">
            Fields resolved
          </p>
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
      <CardContent className="p-3 space-y-3">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Unresolved fields
        </p>

        <div className="space-y-2">
          {fields.map((f) => {
            const resolution = resolutions[f.field];
            const isFieldResolved = !!resolution;

            return (
              <div key={f.field} className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
                {/* Left accent — amber if pending, green if resolved */}
                <div className={`w-1 shrink-0 ${isFieldResolved ? "bg-green-500" : "bg-amber-500"}`} />

                <div className={`px-4 py-3 space-y-2 flex-1 ${isFieldResolved ? "bg-green-500/[0.03]" : "bg-amber-500/[0.03]"}`}>
                  <p className="text-sm font-semibold text-[var(--foreground)]">
                    {f.field}
                    {!isFieldResolved && (
                      <span className="ml-1.5 text-xs font-normal text-amber-600 dark:text-amber-400">
                        ({f.required ? "required" : "optional"}, unmapped)
                      </span>
                    )}
                  </p>

                  {isFieldResolved ? (
                    // ── Resolved inline state ──────────────────────────────
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-green-600 dark:text-green-400 font-medium">
                        {resolution.type === "constant"
                          ? `Constant: ${resolution.value}`
                          : `Mapped to: ${resolution.source_field}`}
                      </span>
                      <button
                        type="button"
                        onClick={() => clearResolution(f.field)}
                        className="text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] underline transition-colors"
                      >
                        change
                      </button>
                    </div>
                  ) : mappingField === f.field ? (
                    // ── Inline field picker ────────────────────────────────
                    <div className="flex items-center gap-2">
                      <select
                        autoFocus
                        defaultValue=""
                        onChange={(e) => {
                          if (!e.target.value) return;
                          resolve(f.field, { type: "field", source_field: e.target.value });
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
                  ) : (
                    // ── Action chips ───────────────────────────────────────
                    <div className="flex flex-wrap gap-2">
                      {f.suggested_constant && inlineChip(
                        `Set constant: ${f.suggested_constant}`,
                        () => resolve(f.field, { type: "constant", value: f.suggested_constant! }),
                      )}
                      {f.suggested_source_field && inlineChip(
                        `Map to: ${f.suggested_source_field}`,
                        () => resolve(f.field, { type: "field", source_field: f.suggested_source_field! }),
                      )}
                      {inlineChip("Map a field", () => setMappingField(f.field))}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Submit all resolutions at once */}
        <Button
          type="button"
          className="w-full"
          disabled={resolvedCount === 0}
          onClick={handleSubmit}
        >
          {resolvedCount === 0
            ? "Resolve fields above to continue"
            : resolvedCount === fields.length
            ? "Continue — all fields resolved"
            : `Continue with ${resolvedCount} of ${fields.length} resolved`}
        </Button>
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
  const pendingChannel = channels.find((ch) => ch.status !== "connected" && ch.status !== "skipped");
  const allSettled = !pendingChannel;

  // Per-channel loading + error state keyed by channel id
  const [connecting, setConnecting] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function handleConnect(ch: ChannelConnectionStatus) {
    const connectorSlug = (ch as Record<string, unknown>).connector_slug as string | undefined ?? ch.id;
    const projectId = (ch as Record<string, unknown>).project_id as string | undefined;

    if (!connectorSlug || !projectId) {
      setErrors((e) => ({ ...e, [ch.id]: "Missing connector or project context." }));
      return;
    }

    setConnecting(ch.id);
    setErrors((e) => ({ ...e, [ch.id]: "" }));

    try {
      const res = await fetch(
        `/api/connections/${connectorSlug}?project_id=${projectId}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`Authorize failed: ${res.status}`);
      const { auth_url }: { auth_url: string } = await res.json();

      const popup = window.open(auth_url, "oauth_popup", "width=600,height=700");
      if (!popup) {
        setErrors((e) => ({ ...e, [ch.id]: "Popup blocked — please allow popups and retry." }));
        setConnecting(null);
        return;
      }

      function onMessage(event: MessageEvent) {
        if (event.data?.type !== "oauth_complete") return;
        window.removeEventListener("message", onMessage);
        if (event.data.success) {
          // Resume the graph — backend re-checks DB and re-interrupts with updated list
          onApprove({ action: "connected", platform_id: ch.id });
        } else {
          setErrors((ev) => ({ ...ev, [ch.id]: event.data.error ?? "Connection failed — please retry." }));
          setConnecting(null);
        }
      }
      window.addEventListener("message", onMessage);
    } catch (err) {
      setErrors((e) => ({ ...e, [ch.id]: err instanceof Error ? err.message : "Unexpected error" }));
      setConnecting(null);
    }
  }

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
            const isSkipped = ch.status === "skipped";
            const isLoading = connecting === ch.id;
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
                  {ch.detail && (
                    <p className="text-xs text-[var(--muted-foreground)] truncate">{ch.detail}</p>
                  )}
                  {errors[ch.id] && (
                    <p className="text-xs text-red-500 mt-0.5">{errors[ch.id]}</p>
                  )}
                </div>

                {/* Status badge or Connect button */}
                {isConnected ? (
                  <span className="shrink-0 rounded-full border border-green-500 px-3 py-1 text-xs font-medium text-green-600 dark:text-green-400">
                    Connected
                  </span>
                ) : isSkipped ? (
                  <span className="shrink-0 rounded-full border border-[var(--border)] px-3 py-1 text-xs font-medium text-[var(--muted-foreground)]">
                    Skipped
                  </span>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    className="shrink-0"
                    disabled={isLoading || connecting !== null}
                    onClick={() => handleConnect(ch)}
                  >
                    {isLoading ? "Opening…" : "Connect"}
                  </Button>
                )}
              </div>
            );
          })}
        </div>

        {/* Primary CTA */}
        {allSettled ? (
          <Button
            type="button"
            className="w-full bg-green-600 hover:bg-green-700 text-white"
            onClick={() => onApprove({ action: "confirm_all" })}
          >
            All settled — continue
          </Button>
        ) : (
          <div className="flex gap-2">
            <Button
              type="button"
              className="flex-1"
              disabled={connecting !== null}
              onClick={() => pendingChannel && handleConnect(pendingChannel)}
            >
              {connecting ? "Opening…" : `Connect ${pendingChannel?.label ?? ""}`}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="flex-1"
              disabled={connecting !== null}
              onClick={() => pendingChannel && onApprove({ action: "skip", platform_id: pendingChannel.id })}
            >
              Skip for now
            </Button>
          </div>
        )}
        {/* DEV-ONLY: bypass OAuth and mark pending channel as connected */}
        {!allSettled && pendingChannel && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full text-xs text-[var(--muted-foreground)] border border-dashed border-[var(--border)] hover:border-orange-400 hover:text-orange-500"
            onClick={() => onApprove({ action: "connected", platform_id: pendingChannel.id })}
          >
            🧪 Dev: mark {pendingChannel.label} as connected (skip OAuth)
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
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-3 space-y-3">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Activate pipeline
        </p>

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


// ── Funnel prompt card ────────────────────────────────────────────────────
// type: "funnel_prompt"
// Resume: { enabled: bool, trigger_field: string | null }

type PicklistFieldOption = { name: string; label: string };

function FunnelPromptCard({ payload, onApprove }: HitlApprovalCardProps) {
  const picklistFields = (payload.picklist_fields ?? []) as PicklistFieldOption[];
  const suggested = (payload.suggested_trigger_field as string | undefined) ?? picklistFields[0]?.name ?? "";
  const infoText = payload.info_text as string | undefined;

  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [triggerField, setTriggerField] = useState<string>(suggested);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Funnel setup
        </p>

        {infoText && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800/60 bg-blue-500/5 px-3 py-2">
            <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">{infoText}</p>
          </div>
        )}

        {/* Enable / skip toggle */}
        <div className="flex gap-2">
          {[
            { value: true,  label: "Yes, set up funnel" },
            { value: false, label: "Skip for now" },
          ].map(({ value, label }) => {
            const isSelected = enabled === value;
            return (
              <button
                key={String(value)}
                type="button"
                onClick={() => setEnabled(value)}
                style={{ borderRadius: isSelected ? "8px" : "9999px" }}
                className={[
                  "flex-1 inline-flex items-center justify-center gap-2 border px-3 py-2 text-sm font-medium",
                  "transition-all duration-300 ease-in-out cursor-pointer",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                    : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:border-[var(--primary)]/40",
                ].join(" ")}
              >
                <span className={[
                  "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-all",
                  isSelected
                    ? "border-[var(--primary)] bg-[var(--primary)]"
                    : "border-[var(--muted-foreground)]/50",
                ].join(" ")}>
                  {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                </span>
                {label}
              </button>
            );
          })}
        </div>

        {/* Trigger field picker — only shown when enabled */}
        {enabled && picklistFields.length > 0 && (
          <div className="space-y-1.5">
            <p className="text-xs font-medium text-[var(--muted-foreground)]">Stage trigger field</p>
            <select
              value={triggerField}
              onChange={(e) => setTriggerField(e.target.value)}
              className="w-full h-9 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] cursor-pointer"
            >
              {picklistFields.map((f) => (
                <option key={f.name} value={f.name}>
                  {f.label || f.name}
                  {f.name === suggested ? " (suggested)" : ""}
                </option>
              ))}
            </select>
          </div>
        )}

        <Button
          type="button"
          className="w-full"
          disabled={enabled === null}
          onClick={() => onApprove({ enabled: enabled ?? false, trigger_field: enabled ? triggerField : null })}
        >
          {enabled === null ? "Choose an option above" : enabled ? "Continue with funnel" : "Skip funnel"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Funnel stages card ────────────────────────────────────────────────────
// type: "funnel_stages"
// Resume: { stages: [{ stage_name, trigger_value, time_field, value_field, per_destination }] }

type FunnelStageRow = {
  stage_name: string;
  trigger_value: string;
  time_field: string;
  value_field: string;
  per_destination: Record<string, { event_name: string }>;
};

function FunnelStagesCard({ payload, onApprove }: HitlApprovalCardProps) {
  const triggerField = payload.trigger_field as string | undefined ?? "Stage";
  const suggestedStages = (payload.suggested_stages ?? []) as Array<{
    stage_name: string; trigger_value: string; time_field?: string; value_field?: string;
    per_destination?: Record<string, unknown>;
  }>;
  const datetimeFields = (payload.datetime_fields ?? []) as string[];
  const numericFields  = (payload.numeric_fields  ?? []) as string[];
  const activeDestinations = (payload.active_destinations ?? []) as string[];
  const infoText = payload.info_text as string | undefined;

  const [stages, setStages] = useState<FunnelStageRow[]>(() =>
    suggestedStages.map((s) => ({
      stage_name:      s.stage_name ?? s.trigger_value ?? "",
      trigger_value:   s.trigger_value ?? "",
      time_field:      s.time_field ?? "",
      value_field:     s.value_field ?? "",
      per_destination: activeDestinations.reduce<Record<string, { event_name: string }>>((acc, d) => {
        acc[d] = { event_name: "" };
        return acc;
      }, {}),
    })),
  );

  function updateStage<K extends keyof FunnelStageRow>(i: number, key: K, value: FunnelStageRow[K]) {
    setStages((prev) => prev.map((s, idx) => idx === i ? { ...s, [key]: value } : s));
  }

  function updateDestEventName(i: number, dest: string, eventName: string) {
    setStages((prev) =>
      prev.map((s, idx) =>
        idx === i
          ? { ...s, per_destination: { ...s.per_destination, [dest]: { event_name: eventName } } }
          : s,
      ),
    );
  }

  const hasStages = stages.length > 0;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Funnel stages — {triggerField}
        </p>

        {infoText && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800/60 bg-blue-500/5 px-3 py-2">
            <p className="text-xs text-blue-700 dark:text-blue-400 leading-relaxed">{infoText}</p>
          </div>
        )}

        {hasStages ? (
          <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
            {stages.map((stage, i) => (
              <div key={i} className="rounded-lg border border-[var(--border)] bg-[var(--background)] p-3 space-y-2">
                {/* Stage name + trigger value header */}
                <div className="flex items-center gap-2">
                  <span className="h-5 w-5 shrink-0 rounded-full bg-[var(--primary)]/10 text-[var(--primary)] text-xs font-bold flex items-center justify-center">
                    {i + 1}
                  </span>
                  <input
                    type="text"
                    value={stage.stage_name}
                    onChange={(e) => updateStage(i, "stage_name", e.target.value)}
                    placeholder="Stage name"
                    className="flex-1 h-8 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                  />
                  <span className="text-[10px] text-[var(--muted-foreground)] bg-[var(--secondary)] px-2 py-0.5 rounded-full shrink-0">
                    {stage.trigger_value}
                  </span>
                </div>

                {/* Optional fields row */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <p className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Time field</p>
                    <select
                      value={stage.time_field}
                      onChange={(e) => updateStage(i, "time_field", e.target.value)}
                      className="w-full h-7 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)] focus:outline-none cursor-pointer"
                    >
                      <option value="">None</option>
                      {datetimeFields.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                  <div>
                    <p className="text-[10px] text-[var(--muted-foreground)] mb-0.5">Value field</p>
                    <select
                      value={stage.value_field}
                      onChange={(e) => updateStage(i, "value_field", e.target.value)}
                      className="w-full h-7 rounded-md border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)] focus:outline-none cursor-pointer"
                    >
                      <option value="">None</option>
                      {numericFields.map((f) => <option key={f} value={f}>{f}</option>)}
                    </select>
                  </div>
                </div>

                {/* Per-destination event name */}
                {activeDestinations.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-[10px] text-[var(--muted-foreground)]">Event name per destination</p>
                    {activeDestinations.map((dest) => (
                      <div key={dest} className="flex items-center gap-2">
                        <span className="text-xs text-[var(--muted-foreground)] w-24 shrink-0 truncate">{dest}</span>
                        <input
                          type="text"
                          value={stage.per_destination[dest]?.event_name ?? ""}
                          onChange={(e) => updateDestEventName(i, dest, e.target.value)}
                          placeholder="e.g. Purchase"
                          className="flex-1 h-7 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 text-xs text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[var(--muted-foreground)] italic">
            No stage values found in schema. Add them manually if needed.
          </p>
        )}

        <Button
          type="button"
          className="w-full"
          disabled={stages.some((s) => !s.stage_name.trim())}
          onClick={() =>
            onApprove({
              stages: stages.map((s) => ({
                stage_name:      s.stage_name.trim(),
                trigger_value:   s.trigger_value,
                time_field:      s.time_field || null,
                value_field:     s.value_field || null,
                per_destination: s.per_destination,
              })),
            })
          }
        >
          {stages.length === 0
            ? "Continue without stages"
            : `Confirm ${stages.length} stage${stages.length !== 1 ? "s" : ""}`}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Validation errors card ────────────────────────────────────────────────
// type: "validation_errors"
// Resume: { action: "edit_mapping" | "skip_errors" | "retry" }

function ValidationErrorsCard({ payload, onApprove }: HitlApprovalCardProps) {
  const errors   = (payload.errors   ?? []) as string[];
  const warnings = (payload.warnings ?? []) as string[];
  const infoText = payload.info_text as string | undefined;
  const hasErrors = errors.length > 0;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-3">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Validation issues
        </p>

        {/* Errors — red */}
        {errors.length > 0 && (
          <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
            <div className="w-1 shrink-0 bg-red-500" />
            <div className="px-4 py-3 flex-1 bg-red-500/[0.03] space-y-1.5">
              <p className="text-xs font-semibold text-red-600 dark:text-red-400 uppercase tracking-wide">
                {errors.length} error{errors.length !== 1 ? "s" : ""}
              </p>
              {errors.map((e, i) => (
                <p key={i} className="text-sm text-[var(--foreground)] leading-snug">{e}</p>
              ))}
            </div>
          </div>
        )}

        {/* Warnings — amber */}
        {warnings.length > 0 && (
          <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
            <div className="w-1 shrink-0 bg-amber-500" />
            <div className="px-4 py-3 flex-1 bg-amber-500/[0.03] space-y-1.5">
              <p className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wide">
                {warnings.length} warning{warnings.length !== 1 ? "s" : ""}
              </p>
              {warnings.map((w, i) => (
                <p key={i} className="text-sm text-[var(--muted-foreground)] leading-snug">{w}</p>
              ))}
            </div>
          </div>
        )}

        {infoText && (
          <p className="text-xs text-[var(--muted-foreground)]">{infoText}</p>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <Button
            type="button"
            className="flex-1"
            onClick={() => onApprove({ action: "edit_mapping" })}
          >
            Fix mapping
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => onApprove({ action: "retry" })}
          >
            Retry
          </Button>
        </div>
        {hasErrors && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full text-xs text-[var(--muted-foreground)] border border-dashed border-[var(--border)] hover:border-amber-400 hover:text-amber-500"
            onClick={() => onApprove({ action: "skip_errors" })}
          >
            Skip errors and proceed anyway
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ── Activation confirm card (token-gated) ─────────────────────────────────
// type: "activation_confirm"
// Resume: { token: str }  — user must type back the UUID token shown

function ActivationConfirmTokenCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const token          = (payload.token          as string | undefined) ?? "";
  const summary        = (payload.summary        as string[] | undefined) ?? [];
  const infoText       = (payload.info_text      as string | undefined);
  const confirmLabel   = (payload.confirm_label  as string | undefined) ?? "Activate";
  const secondaryLabel = (payload.secondary_label as string | undefined) ?? "Go back";

  const [input, setInput] = useState("");
  const matches = input.trim() === token;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Confirm activation
        </p>

        {/* Summary block — green left border */}
        {summary.length > 0 && (
          <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden">
            <div className="w-1 shrink-0 bg-green-500" />
            <div className="px-4 py-3 flex-1 bg-green-500/[0.03] space-y-1">
              {summary.map((line, i) => (
                <p key={i} className="text-sm text-[var(--foreground)] leading-snug">{line}</p>
              ))}
            </div>
          </div>
        )}

        {/* Confirmation token — monospace, prominent */}
        <div className="rounded-lg border border-[var(--border)] bg-[var(--secondary)] px-4 py-3 space-y-1">
          <p className="text-[10px] font-semibold text-[var(--muted-foreground)] uppercase tracking-widest">
            Confirmation code
          </p>
          <p className="font-mono text-sm font-semibold text-[var(--foreground)] select-all break-all">
            {token}
          </p>
        </div>

        {infoText && (
          <p className="text-xs text-[var(--muted-foreground)]">{infoText}</p>
        )}

        {/* Token input */}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type the code above to confirm…"
          className={[
            "w-full h-9 rounded-lg border px-3 text-sm font-mono bg-[var(--background)] text-[var(--foreground)]",
            "focus:outline-none focus:ring-1 transition-colors",
            input && !matches
              ? "border-red-400 focus:ring-red-400"
              : matches
              ? "border-green-500 focus:ring-green-500"
              : "border-[var(--border)] focus:ring-[var(--primary)]",
          ].join(" ")}
        />

        {input && !matches && (
          <p className="text-xs text-red-500 -mt-2">Code does not match — check for typos.</p>
        )}

        <div className="flex gap-2">
          <Button
            type="button"
            className="flex-1"
            disabled={!matches}
            onClick={() => onApprove({ token: input.trim() })}
          >
            {matches ? confirmLabel : "Enter code to activate"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="flex-1"
            onClick={() => onReject("go_back")}
          >
            {secondaryLabel}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Connect source card (OAuth handoff) ──────────────────────────────────

function ConnectSourceCard({ payload, onApprove }: HitlApprovalCardProps) {
  const sourceLabel  = payload.source_label  ?? "Source";
  const connectorSlug = payload.connector_slug as string | undefined;
  const projectId    = payload.project_id    as string | undefined;
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState<string | null>(null);

  async function handleConnect() {
    if (!connectorSlug || !projectId) {
      setError("Missing connector or project context.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Route through the Next.js BFF so the httpOnly JWT is forwarded
      const res = await fetch(
        `/api/connections/${connectorSlug}?project_id=${projectId}`,
        { method: "POST" },
      );
      if (!res.ok) throw new Error(`Authorize failed: ${res.status}`);
      const { auth_url }: { auth_url: string } = await res.json();

      // Open OAuth popup and wait for postMessage from callback
      const popup = window.open(auth_url, "oauth_popup", "width=600,height=700");
      if (!popup) {
        setError("Popup was blocked. Please allow popups for this site.");
        setLoading(false);
        return;
      }

      function onMessage(event: MessageEvent) {
        if (event.data?.type !== "oauth_complete") return;
        window.removeEventListener("message", onMessage);
        if (event.data.success) {
          onApprove({ action: "connected", connector_slug: connectorSlug });
        } else {
          setError(event.data.error ?? "Connection failed. Please try again.");
          setLoading(false);
        }
      }
      window.addEventListener("message", onMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
      setLoading(false);
    }
  }

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-3">
        {/* Info block with red left border */}
        <div className="flex rounded-md border border-[var(--border)]/60 overflow-hidden mb-3">
          <div className="w-1 shrink-0 bg-red-500" />
          <div className="px-4 py-3 space-y-0.5 flex-1 bg-red-500/[0.03]">
            <p className="text-sm font-semibold text-[var(--foreground)]">{sourceLabel}</p>
            <p className="text-sm text-[var(--muted-foreground)] leading-relaxed">
              {(payload.message as string | undefined) ?? `Connect your ${sourceLabel} account to continue.`}
            </p>
            {error && (
              <p className="text-xs text-red-600 dark:text-red-400 mt-1">{error}</p>
            )}
          </div>
        </div>

        <Button
          type="button"
          className="w-full"
          disabled={loading}
          onClick={handleConnect}
        >
          {loading ? "Opening…" : `Connect ${sourceLabel}`}
        </Button>
      </CardContent>
    </Card>
  );
}


// ── Mapping matrix card ───────────────────────────────────────────────────
function MappingMatrixCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const rows = (payload.rows ?? []) as Array<{
    canonical_key: string; label: string; source_field: string | null;
    status: string; cells: Record<string, { field: string | null; status: string }>;
  }>;
  const destinations = (payload.destinations ?? []) as Array<{ id: string; label: string }>;
  const sourceFields = (payload.source_fields ?? []) as string[];

  const [overrides, setOverrides] = useState<Record<string, string>>(() =>
    Object.fromEntries(rows.map((r) => [r.canonical_key, r.source_field ?? ""]))
  );

  function setField(canonicalKey: string, value: string) {
    setOverrides((prev) => ({ ...prev, [canonicalKey]: value }));
  }

  const missingRequired = rows.filter(
    (r) => r.status === "missing" && !overrides[r.canonical_key]
  ).length;

  function handleApprove() {
    const updatedRows = rows.map((r) => ({
      ...r,
      source_field: overrides[r.canonical_key] || r.source_field,
    }));
    onApprove({ rows: updatedRows });
  }

  const statusDot = (status: string) => {
    const cls =
      status === "mapped"      ? "bg-green-500" :
      status === "needs_input" ? "bg-amber-500" :
      status === "missing"     ? "bg-red-500"   : "bg-[var(--muted-foreground)]/30";
    return <span className={`h-2 w-2 rounded-full shrink-0 inline-block ${cls}`} />;
  };

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Mapping matrix
        </p>

        <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
          <table className="w-full text-sm" style={{ tableLayout: "fixed" }}>
            <thead>
              <tr className="bg-[var(--secondary)]">
                <th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)] w-36">
                  What Signals needs
                </th>
                <th className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)] w-44 border-l border-[var(--border)]">
                  Your SF field
                </th>
                {destinations.map((d) => (
                  <th key={d.id} className="px-3 py-2 text-left text-xs font-medium text-[var(--muted-foreground)] border-l border-[var(--border)] w-28">
                    {d.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => {
                const currentSource = overrides[row.canonical_key] ?? "";
                return (
                  <tr key={row.canonical_key} className={`border-t border-[var(--border)] ${i % 2 === 0 ? "" : "bg-[var(--secondary)]/30"}`}>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center gap-1.5">
                        {statusDot(overrides[row.canonical_key] ? "mapped" : row.status)}
                        <span className="text-xs font-medium text-[var(--foreground)] truncate">{row.label}</span>
                      </div>
                    </td>
                    <td className="px-3 py-2 border-l border-[var(--border)]">
                      {sourceFields.length > 0 ? (
                        <select
                          value={currentSource}
                          onChange={(e) => setField(row.canonical_key, e.target.value)}
                          className="w-full h-7 rounded border border-[var(--border)] bg-[var(--background)] px-2 text-xs text-[var(--foreground)] focus:outline-none cursor-pointer"
                        >
                          <option value="">— not mapped —</option>
                          {sourceFields.map((f) => <option key={f} value={f}>{f}</option>)}
                        </select>
                      ) : (
                        <span className="text-xs text-[var(--foreground)] truncate">{currentSource || "—"}</span>
                      )}
                    </td>
                    {destinations.map((d) => {
                      const cell = row.cells[d.id];
                      return (
                        <td key={d.id} className="px-3 py-2 border-l border-[var(--border)]">
                          <div className="flex items-center gap-1.5">
                            {cell ? statusDot(currentSource ? "mapped" : cell.status) : null}
                            <span className="text-xs text-[var(--muted-foreground)] truncate">
                              {cell?.field ?? (cell ? "—" : "n/a")}
                            </span>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {[
            { color: "bg-green-500", label: "mapped" },
            { color: "bg-amber-500", label: "needs input" },
            { color: "bg-red-500",   label: "missing (required)" },
          ].map(({ color, label }) => (
            <span key={label} className="flex items-center gap-1 text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider">
              <span className={`h-2 w-2 rounded-full ${color}`} /> {label}
            </span>
          ))}
        </div>

        <div className="flex gap-2">
          <Button type="button" className="flex-1" onClick={handleApprove}>
            {missingRequired > 0
              ? `Continue with ${missingRequired} field${missingRequired !== 1 ? "s" : ""} unmapped`
              : "Approve mapping"}
          </Button>
          <Button type="button" variant="outline" className="flex-1" onClick={() => onReject("edit_manual")}>
            Edit manually
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Google Ads account picker card ────────────────────────────────────────
function GoogleAdsAccountCard({ payload, onApprove }: HitlApprovalCardProps) {
  const accounts = (payload.accounts ?? []) as Array<{ value: string; label: string }>;
  const infoText = payload.info_text as string | undefined;
  const [selected, setSelected] = useState<string>(accounts[0]?.value ?? "");
  const selectedAccount = accounts.find((a) => a.value === selected);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Google Ads account
        </p>
        {infoText && (
          <div className="rounded-lg border border-blue-200 dark:border-blue-800/60 bg-blue-500/5 px-3 py-2">
            <p className="text-xs text-blue-700 dark:text-blue-400">{infoText}</p>
          </div>
        )}
        {accounts.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)] italic">No Google Ads accounts found.</p>
        ) : (
          <div className="space-y-2">
            {accounts.map((acc) => {
              const isSelected = selected === acc.value;
              return (
                <button
                  key={acc.value}
                  type="button"
                  onClick={() => setSelected(acc.value)}
                  style={{ borderRadius: isSelected ? "8px" : "9999px" }}
                  className={[
                    "w-full inline-flex items-center gap-2 border px-3 py-2 text-sm font-medium text-left",
                    "transition-all duration-300 cursor-pointer",
                    isSelected
                      ? "border-[var(--primary)] bg-[var(--primary)]/10 text-[var(--primary)]"
                      : "border-[var(--border)] bg-[var(--background)] text-[var(--foreground)] hover:bg-[var(--secondary)]",
                  ].join(" ")}
                >
                  <span className={[
                    "flex h-4 w-4 shrink-0 items-center justify-center rounded-full border transition-all",
                    isSelected ? "border-[var(--primary)] bg-[var(--primary)]" : "border-[var(--muted-foreground)]/50",
                  ].join(" ")}>
                    {isSelected && <span className="h-1.5 w-1.5 rounded-full bg-white" />}
                  </span>
                  <div className="min-w-0">
                    <p className="truncate">{acc.label}</p>
                    <p className="text-xs text-[var(--muted-foreground)] truncate">{acc.value}</p>
                  </div>
                </button>
              );
            })}
          </div>
        )}
        <Button
          type="button"
          className="w-full"
          disabled={!selected}
          onClick={() => onApprove({ account_id: selected, account_label: selectedAccount?.label ?? selected })}
        >
          {selected ? `Use account ${selectedAccount?.label ?? selected}` : "Select an account"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Google conversion action picker card ──────────────────────────────────
function GoogleConversionActionCard({ payload, onApprove }: HitlApprovalCardProps) {
  const actions = (payload.conversion_actions ?? []) as Array<{ value: string; label: string }>;
  const accountId = payload.account_id as string | undefined;
  const [selected, setSelected] = useState<string>(actions[0]?.value ?? "");
  const selectedAction = actions.find((a) => a.value === selected);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          Conversion action
        </p>
        {accountId && (
          <p className="text-xs text-[var(--muted-foreground)]">Account: {accountId}</p>
        )}
        {actions.length === 0 ? (
          <p className="text-sm text-[var(--muted-foreground)] italic">No conversion actions found.</p>
        ) : (
          <select
            value={selected}
            onChange={(e) => setSelected(e.target.value)}
            className="w-full h-9 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)] cursor-pointer"
          >
            {!selected && <option value="" disabled>Select a conversion action…</option>}
            {actions.map((a) => (
              <option key={a.value} value={a.value}>{a.label}</option>
            ))}
          </select>
        )}
        <Button
          type="button"
          className="w-full"
          disabled={!selected}
          onClick={() => onApprove({ conversion_action: selected, conversion_action_label: selectedAction?.label ?? selected })}
        >
          {selected ? `Use ${selectedAction?.label ?? selected}` : "Select a conversion action"}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Coverage breakdown card ───────────────────────────────────────────────
function CoverageBreakdownCard({ payload, onApprove, onReject }: HitlApprovalCardProps) {
  const destinations = (payload.destinations_breakdown ?? payload.destinations ?? []) as Array<{
    destination: string; coverage_pct: number; match_keys_covered: string[];
    match_keys_missing: string[]; status: string; required_count: number; mapped_count: number;
  }>;
  const overallPct = (payload.overall_pct as number | undefined) ?? 0;

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
            Coverage breakdown
          </p>
          <span className={`text-sm font-semibold ${overallPct >= 80 ? "text-green-600 dark:text-green-400" : overallPct >= 50 ? "text-amber-600 dark:text-amber-400" : "text-red-500"}`}>
            {overallPct.toFixed(0)}% overall
          </span>
        </div>

        <div className="space-y-2">
          {destinations.map((dest) => {
            const pct = dest.coverage_pct;
            const barColor = pct >= 80 ? "bg-green-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
            return (
              <div key={dest.destination} className="rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2.5 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-[var(--foreground)]">
                    {dest.destination.replace(/_/g, " ").toUpperCase()}
                  </span>
                  <span className={`text-xs font-semibold ${dest.status === "ready" ? "text-green-600 dark:text-green-400" : "text-amber-600 dark:text-amber-400"}`}>
                    {pct.toFixed(0)}% — {dest.mapped_count}/{dest.required_count} fields
                  </span>
                </div>
                <div className="h-1.5 rounded-full bg-[var(--secondary)] overflow-hidden">
                  <div className={`h-full rounded-full transition-all ${barColor}`} style={{ width: `${pct}%` }} />
                </div>
                {dest.match_keys_missing.length > 0 && (
                  <p className="text-xs text-amber-600 dark:text-amber-400">
                    Missing match keys: {dest.match_keys_missing.join(", ")}
                  </p>
                )}
                {dest.match_keys_covered.length > 0 && dest.match_keys_missing.length === 0 && (
                  <p className="text-xs text-green-600 dark:text-green-400">
                    All match keys covered: {dest.match_keys_covered.join(", ")}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex gap-2">
          <Button type="button" className="flex-1" onClick={() => onApprove({ acknowledged: true })}>
            Continue
          </Button>
          <Button type="button" variant="outline" className="flex-1" onClick={() => onReject("fix_mapping")}>
            Fix mapping
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Canonical needs card ──────────────────────────────────────────────────
function CanonicalNeedsCard({ payload, onApprove }: HitlApprovalCardProps) {
  const needs = (payload.needs ?? []) as Array<{
    canonical_key: string; label: string; reason: string; status: string; required: boolean;
  }>;
  const missing = needs.filter((n) => n.status === "missing");
  const mapped = needs.filter((n) => n.status === "mapped");

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
            What Signals needs
          </p>
          <span className="text-xs text-[var(--muted-foreground)]">
            {mapped.length}/{needs.length} mapped
          </span>
        </div>

        <div className="space-y-1.5">
          {needs.map((n) => (
            <div
              key={n.canonical_key}
              className={`flex items-start gap-2.5 rounded-lg border px-3 py-2 ${
                n.status === "mapped"
                  ? "border-green-200 dark:border-green-800/50 bg-green-500/5"
                  : n.required
                  ? "border-red-200 dark:border-red-800/50 bg-red-500/5"
                  : "border-[var(--border)] bg-[var(--background)]"
              }`}
            >
              <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${
                n.status === "mapped" ? "bg-green-500" : n.required ? "bg-red-500" : "bg-amber-500"
              }`} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--foreground)]">{n.label}</p>
                {n.reason && (
                  <p className="text-xs text-[var(--muted-foreground)] leading-relaxed">{n.reason}</p>
                )}
              </div>
              <span className={`shrink-0 text-xs font-medium ${
                n.status === "mapped" ? "text-green-600 dark:text-green-400" : "text-[var(--muted-foreground)]"
              }`}>
                {n.status === "mapped" ? "mapped" : n.required ? "required" : "optional"}
              </span>
            </div>
          ))}
        </div>

        <Button
          type="button"
          className="w-full"
          onClick={() => onApprove({ acknowledged: true })}
        >
          {missing.length === 0 ? "All fields mapped — continue" : `Continue with ${missing.length} unmapped`}
        </Button>
      </CardContent>
    </Card>
  );
}

// ── Validation dry-run card (enhanced with named checks + sample payloads) ─
function ValidationDryRunCard({ payload, onApprove }: HitlApprovalCardProps) {
  const checks = (payload.checks ?? []) as Array<{
    name: string; passed: boolean; severity: string; message: string;
    sample_payload?: Record<string, unknown>;
  }>;
  const overallPassed = payload.overall_passed as boolean | undefined;
  const infoText = payload.info_text as string | undefined;
  const [expanded, setExpanded] = useState<string | null>(null);

  const errors = checks.filter((c) => !c.passed && c.severity === "error");

  return (
    <Card className="border-[var(--border)] bg-[var(--card)] overflow-hidden shadow-sm">
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
            Validation results
          </p>
          <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
            overallPassed
              ? "bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400"
              : "bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400"
          }`}>
            {overallPassed ? "Passed" : `${errors.length} issue${errors.length !== 1 ? "s" : ""}`}
          </span>
        </div>

        {infoText && (
          <p className="text-xs text-[var(--muted-foreground)]">{infoText}</p>
        )}

        <div className="space-y-1.5">
          {checks.map((check) => {
            const isExpanded = expanded === check.name;
            const hasSample = check.sample_payload && Object.keys(check.sample_payload).length > 0;
            const accent =
              check.passed ? "border-green-200 dark:border-green-800/50 bg-green-500/[0.03]" :
              check.severity === "error" ? "border-red-200 dark:border-red-800/50 bg-red-500/[0.03]" :
              "border-amber-200 dark:border-amber-800/50 bg-amber-500/[0.03]";
            const dot =
              check.passed ? "bg-green-500" :
              check.severity === "error" ? "bg-red-500" : "bg-amber-500";

            return (
              <div key={check.name} className={`rounded-lg border overflow-hidden ${accent}`}>
                <button
                  type="button"
                  className="w-full flex items-start gap-2.5 px-3 py-2 text-left cursor-pointer"
                  onClick={() => hasSample && setExpanded(isExpanded ? null : check.name)}
                >
                  <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${dot}`} />
                  <span className="flex-1 text-sm text-[var(--foreground)] leading-snug">{check.message}</span>
                  {hasSample && (
                    <span className="text-[10px] text-[var(--muted-foreground)] shrink-0 mt-0.5">
                      {isExpanded ? "hide" : "sample"}
                    </span>
                  )}
                </button>
                {isExpanded && hasSample && (
                  <div className="border-t border-[var(--border)]/50 px-3 py-2 bg-[var(--background)]">
                    <p className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-1.5">
                      Sample payload (masked)
                    </p>
                    <pre className="text-xs text-[var(--foreground)] overflow-x-auto whitespace-pre-wrap break-all">
                      {JSON.stringify(check.sample_payload, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <div className="flex gap-2">
          <Button type="button" className="flex-1" onClick={() => onApprove({ action: "edit_mapping" })}>
            Fix mapping
          </Button>
          <Button type="button" variant="outline" className="flex-1" onClick={() => onApprove({ action: "retry" })}>
            Retry
          </Button>
        </div>
        {errors.length > 0 && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full text-xs text-[var(--muted-foreground)] border border-dashed border-[var(--border)] hover:border-amber-400 hover:text-amber-500"
            onClick={() => onApprove({ action: "skip_errors" })}
          >
            Skip errors and proceed anyway
          </Button>
        )}
      </CardContent>
    </Card>
  );
}

// ── Destination metadata collection card ─────────────────────────────────
function DestinationMetadataCard({ payload, onApprove }: HitlApprovalCardProps) {
  const destLabel = (payload.destination_label as string | undefined) ?? "destination";
  const fields = (payload.fields ?? []) as Array<{
    name: string; label: string; placeholder?: string; required?: boolean;
  }>;

  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map((f) => [f.name, ""]))
  );

  const requiredFilled = fields
    .filter((f) => f.required)
    .every((f) => (values[f.name] || "").trim().length > 0);

  return (
    <Card className="border-[var(--border)] bg-[var(--card)]">
      <CardContent className="p-4 space-y-4">
        <p className="text-[10px] font-semibold tracking-widest text-[var(--muted-foreground)] uppercase">
          {destLabel} setup
        </p>

        <div className="space-y-3">
          {fields.map((f) => (
            <div key={f.name} className="space-y-1">
              <label className="text-xs font-medium text-[var(--foreground)]">
                {f.label}
                {f.required && <span className="text-red-500 ml-0.5">*</span>}
              </label>
              <input
                type="text"
                value={values[f.name] ?? ""}
                onChange={(e) => setValues((prev) => ({ ...prev, [f.name]: e.target.value }))}
                placeholder={f.placeholder ?? `Enter ${f.label.toLowerCase()}…`}
                className="w-full h-9 rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 text-sm text-[var(--foreground)] focus:outline-none focus:ring-1 focus:ring-[var(--primary)]"
              />
            </div>
          ))}
        </div>

        <Button
          type="button"
          className="w-full"
          disabled={!requiredFilled}
          onClick={() => onApprove({ metadata: values })}
        >
          {requiredFilled ? `Save ${destLabel} settings` : "Fill required fields above"}
        </Button>
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
    case "connect_source":
      return <ConnectSourceCard {...cardProps} />;
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
    // ── Funnel phase interrupts ────────────────────────────────────────────
    case "funnel_prompt":
      return <FunnelPromptCard {...cardProps} />;
    case "funnel_stages":
      return <FunnelStagesCard {...cardProps} />;
    // ── Validation phase interrupts ────────────────────────────────────────
    case "validation_errors":
      return <ValidationErrorsCard {...cardProps} />;
    // ── Token-gated activation confirm ─────────────────────────────────────
    case "activation_confirm":
      return <ActivationConfirmTokenCard {...cardProps} />;
    // ── New interrupt types ────────────────────────────────────────────────
    case "mapping_matrix":
      return <MappingMatrixCard {...cardProps} />;
    case "google_ads_account":
      return <GoogleAdsAccountCard {...cardProps} />;
    case "google_conversion_action":
      return <GoogleConversionActionCard {...cardProps} />;
    case "coverage_breakdown":
      return <CoverageBreakdownCard {...cardProps} />;
    case "canonical_needs":
      return <CanonicalNeedsCard {...cardProps} />;
    case "validation_dry_run":
      return <ValidationDryRunCard {...cardProps} />;
    case "destination_metadata":
      return <DestinationMetadataCard {...cardProps} />;
    default:
      return null;
  }
}
