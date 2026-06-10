"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";

import { apiClient } from "@/lib/api-client";
import type { MappingSessionDetail } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

interface MappingDetailPageProps {
  params: Promise<{ id: string }>;
}

function confidenceVariant(confidence: number) {
  if (confidence >= 0.85) return "success" as const;
  if (confidence >= 0.5) return "warning" as const;
  return "error" as const;
}

function statusVariant(status: string) {
  switch (status) {
    case "auto_approved":
    case "completed":
      return "success" as const;
    case "needs_review":
      return "warning" as const;
    case "failed":
      return "error" as const;
    default:
      return "default" as const;
  }
}

export default function MappingDetailPage({ params }: MappingDetailPageProps) {
  const { id } = use(params);

  const [data, setData] = useState<MappingSessionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const detail = await apiClient.get<MappingSessionDetail>(
          `/mappings/${id}`,
        );
        if (!cancelled) setData(detail);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "load_failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 p-4 text-sm text-[var(--destructive)]">
        {error ?? "not_found"}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/mappings"
          className="text-sm text-[var(--muted-foreground)] underline-offset-4 hover:underline"
        >
          &larr; Back to mappings
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">
          {data.source_object} &rarr; {data.destination_type}
        </h1>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Run metadata</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 text-sm">
          <Meta label="Session ID" value={String(data.id)} />
          <Meta label="Source" value={data.source} />
          <Meta label="Kind" value={data.mapping_kind} />
          <Meta
            label="Status"
            value={<Badge variant={statusVariant(data.status)}>{data.status}</Badge>}
          />
          <Meta
            label="Created"
            value={new Date(data.created_at).toLocaleString()}
          />
          <Meta
            label="Canonical parent"
            value={data.canonical_session_id?.toString() ?? "—"}
          />
        </CardContent>
      </Card>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">
          Field mappings ({data.field_mappings.length})
        </h2>
        <div className="overflow-hidden rounded-[var(--radius)] border border-[var(--border)]">
          <table className="w-full text-sm">
            <thead className="bg-[var(--secondary)] text-left text-xs uppercase text-[var(--muted-foreground)]">
              <tr>
                <th className="px-4 py-2 font-medium">Source field</th>
                <th className="px-4 py-2 font-medium">Destination field</th>
                <th className="px-4 py-2 font-medium">Confidence</th>
                <th className="px-4 py-2 font-medium">Status</th>
                <th className="px-4 py-2 font-medium">Validation</th>
              </tr>
            </thead>
            <tbody>
              {data.field_mappings.length === 0 ? (
                <tr>
                  <td
                    colSpan={5}
                    className="px-4 py-8 text-center text-sm text-[var(--muted-foreground)]"
                  >
                    No field mappings recorded.
                  </td>
                </tr>
              ) : (
                data.field_mappings.map((fm) => (
                  <tr
                    key={fm.id}
                    className="border-t border-[var(--border)] hover:bg-[var(--secondary)]/50"
                  >
                    <td className="px-4 py-3 font-mono text-xs">
                      {fm.source_field}
                    </td>
                    <td className="px-4 py-3 font-mono text-xs">
                      {fm.destination_field ?? "—"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={confidenceVariant(fm.confidence)}>
                        {(fm.confidence * 100).toFixed(0)}%
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant(fm.status)}>
                        {fm.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-[var(--muted-foreground)]">
                      {fm.validation_status}
                      {fm.validation_notes.length > 0 ? (
                        <span className="ml-2 italic">
                          {fm.validation_notes.join(", ")}
                        </span>
                      ) : null}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Meta({
  label,
  value,
}: {
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-xs uppercase text-[var(--muted-foreground)]">
        {label}
      </div>
      <div className="mt-1">{value}</div>
    </div>
  );
}
