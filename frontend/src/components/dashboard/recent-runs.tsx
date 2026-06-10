"use client";

import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import type { MappingSessionRead } from "@/lib/types";

interface RecentRunsProps {
  items: MappingSessionRead[];
}

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

export function RecentRuns({ items }: RecentRunsProps) {
  if (items.length === 0) {
    return (
      <div className="rounded-[var(--radius)] border border-dashed border-[var(--border)] p-8 text-center text-sm text-[var(--muted-foreground)]">
        No mapping runs yet. Start a chat from the Chat tab.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border)]">
      <table className="w-full text-sm">
        <thead className="bg-[var(--secondary)] text-left text-xs uppercase text-[var(--muted-foreground)]">
          <tr>
            <th className="px-4 py-2 font-medium">Created</th>
            <th className="px-4 py-2 font-medium">Source</th>
            <th className="px-4 py-2 font-medium">Destination</th>
            <th className="px-4 py-2 font-medium">Status</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr
              key={row.id}
              className="border-t border-[var(--border)] hover:bg-[var(--secondary)]/50"
            >
              <td className="px-4 py-3 whitespace-nowrap">
                {new Date(row.created_at).toLocaleString()}
              </td>
              <td className="px-4 py-3">{row.source_object}</td>
              <td className="px-4 py-3">{row.destination_type}</td>
              <td className="px-4 py-3">
                <Badge variant={statusVariant(row.status)}>{row.status}</Badge>
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  href={`/mappings/${row.id}`}
                  className="text-sm underline-offset-4 hover:underline"
                >
                  View
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
