"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";

import { apiClient, ApiError } from "@/lib/api-client";
import type {
  MappingSessionListResponse,
  MappingSessionRead,
} from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

const PAGE_SIZE = 20;

function statusVariant(status: string) {
  switch (status) {
    case "completed":
    case "auto_approved":
      return "success" as const;
    case "needs_review":
      return "warning" as const;
    case "failed":
      return "error" as const;
    default:
      return "default" as const;
  }
}

export function MappingsTable() {
  const [items, setItems] = useState<MappingSessionRead[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);

  async function load(nextOffset: number) {
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.get<MappingSessionListResponse>(
        `/mappings?limit=${PAGE_SIZE}&offset=${nextOffset}`,
      );
      setItems(data.items);
      setTotal(data.total);
      setOffset(nextOffset);
    } catch (err) {
      setError(err instanceof Error ? err.message : "load_failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(0);
  }, []);

  async function onDelete(id: number) {
    if (!confirm("Delete this mapping run? This cannot be undone.")) return;
    setDeleting(id);
    try {
      await apiClient.delete(`/mappings/${id}`);
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

  const columns = useMemo<ColumnDef<MappingSessionRead>[]>(
    () => [
      {
        accessorKey: "created_at",
        header: "Created",
        cell: (info) =>
          new Date(info.getValue<string>()).toLocaleString(),
      },
      { accessorKey: "source_object", header: "Source" },
      { accessorKey: "destination_type", header: "Destination" },
      { accessorKey: "mapping_kind", header: "Kind" },
      {
        accessorKey: "status",
        header: "Status",
        cell: (info) => (
          <Badge variant={statusVariant(info.getValue<string>())}>
            {info.getValue<string>()}
          </Badge>
        ),
      },
      {
        id: "actions",
        header: "",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="flex justify-end gap-2">
              <Link
                href={`/mappings/${row.id}`}
                className="text-sm underline-offset-4 hover:underline"
              >
                View
              </Link>
              <button
                type="button"
                onClick={() => onDelete(row.id)}
                disabled={deleting === row.id}
                className="text-sm text-[var(--destructive)] underline-offset-4 hover:underline disabled:opacity-50"
              >
                {deleting === row.id ? "..." : "Delete"}
              </button>
            </div>
          );
        },
      },
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [deleting, offset],
  );

  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const page = Math.floor(offset / PAGE_SIZE) + 1;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));

  if (loading && items.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error ? (
        <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
          {error}
        </div>
      ) : null}

      <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border)]">
        <table className="w-full text-sm">
          <thead className="bg-[var(--secondary)] text-left text-xs uppercase text-[var(--muted-foreground)]">
            {table.getHeaderGroups().map((hg) => (
              <tr key={hg.id}>
                {hg.headers.map((header) => (
                  <th key={header.id} className="px-4 py-2 font-medium">
                    {flexRender(
                      header.column.columnDef.header,
                      header.getContext(),
                    )}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]"
                >
                  No mappings.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  className="border-t border-[var(--border)] hover:bg-[var(--secondary)]/50"
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between text-sm">
        <span className="text-[var(--muted-foreground)]">
          Page {page} of {pageCount} ({total} total)
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
    </div>
  );
}
