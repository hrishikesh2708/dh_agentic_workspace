"use client";

import { useCallback, useEffect, useState } from "react";

import { apiClient, ApiError } from "@/lib/api-client";
import type { GoldenRuleListResponse, GoldenRuleRead } from "@/lib/types";
import { AddRuleDialog } from "./add-rule-dialog";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

const PAGE_SIZE = 25;

export function GoldenRulesTable() {
  const [items, setItems] = useState<GoldenRuleRead[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [deleting, setDeleting] = useState<number | null>(null);

  const load = useCallback(async (nextOffset: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<GoldenRuleListResponse>(
        `/golden-rules?limit=${PAGE_SIZE}&offset=${nextOffset}`,
      );
      setItems(data.items);
      setTotal(data.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load_failed");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(0);
  }, [load]);

  async function onDelete(id: number) {
    if (!confirm("Delete this golden rule?")) return;
    setDeleting(id);
    try {
      await apiClient.delete(`/golden-rules/${id}`);
      await load(offset);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("delete_failed");
      }
    } finally {
      setDeleting(null);
    }
  }

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-[var(--muted-foreground)]">
          {total} rule{total === 1 ? "" : "s"} learned so far.
        </p>
        <Button onClick={() => setOpen(true)}>Add rule</Button>
      </div>

      {error ? (
        <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
          {error}
        </div>
      ) : null}

      {loading && items.length === 0 ? (
        <div className="flex h-64 items-center justify-center">
          <Spinner />
        </div>
      ) : (
        <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--secondary)] text-left text-xs uppercase text-[var(--muted-foreground)]">
              <tr>
                <th className="px-4 py-2 font-medium">Source pattern</th>
                <th className="px-4 py-2 font-medium">Destination field</th>
                <th className="px-4 py-2 font-medium">Destination type</th>
                <th className="px-4 py-2 font-medium">Count</th>
                <th className="px-4 py-2 font-medium">Created</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]"
                  >
                    No golden rules yet.
                  </td>
                </tr>
              ) : (
                items.map((row) => (
                  <tr
                    key={row.id}
                    className="border-t border-[var(--border)] hover:bg-[var(--secondary)]/50"
                  >
                    <td className="px-4 py-3 font-mono text-xs">
                      {row.source_pattern}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {row.destination_field}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {row.destination_type}
                    </td>
                    <td className="px-4 py-3">{row.occurrence_count}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-[var(--muted-foreground)]">
                      {new Date(row.created_at).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button
                        type="button"
                        onClick={() => onDelete(row.id)}
                        disabled={deleting === row.id}
                        className="text-sm text-[var(--destructive)] underline-offset-4 hover:underline disabled:opacity-50"
                      >
                        {deleting === row.id ? "..." : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <span className="text-[var(--muted-foreground)]">
          Page {page} of {pageCount}
        </span>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={offset === 0 || loading}
            onClick={() => load(Math.max(0, offset - PAGE_SIZE))}
          >
            Previous
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={offset + PAGE_SIZE >= total || loading}
            onClick={() => load(offset + PAGE_SIZE)}
          >
            Next
          </Button>
        </div>
      </div>

      <AddRuleDialog
        open={open}
        onOpenChange={setOpen}
        onCreated={() => load(0)}
      />
    </div>
  );
}
