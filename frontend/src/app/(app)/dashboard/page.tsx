"use client";

import { useEffect, useMemo, useState } from "react";

import { StatCard } from "@/components/dashboard/stat-card";
import { RecentRuns } from "@/components/dashboard/recent-runs";
import { Spinner } from "@/components/ui/spinner";
import { apiClient } from "@/lib/api-client";
import type {
  GoldenRuleListResponse,
  MappingSessionListResponse,
  MappingSessionRead,
} from "@/lib/types";

interface DashboardData {
  mappings: MappingSessionRead[];
  total: number;
  goldenRulesTotal: number;
}

const ONE_WEEK_MS = 7 * 24 * 60 * 60 * 1000;

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [mappings, golden] = await Promise.all([
          apiClient.get<MappingSessionListResponse>(
            "/mappings?limit=20&offset=0",
          ),
          apiClient.get<GoldenRuleListResponse>(
            "/golden-rules?limit=1&offset=0",
          ),
        ]);
        if (cancelled) return;
        setData({
          mappings: mappings.items,
          total: mappings.total,
          goldenRulesTotal: golden.total,
        });
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "load_failed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const stats = useMemo(() => {
    if (!data) {
      return { total: 0, thisWeek: 0, autoApprovedPct: 0, golden: 0 };
    }
    const total = data.total;
    const cutoff = Date.now() - ONE_WEEK_MS;
    const thisWeek = data.mappings.filter(
      (m) => new Date(m.created_at).getTime() >= cutoff,
    ).length;
    const autoApproved = data.mappings.filter(
      (m) => m.status === "auto_approved" || m.status === "completed",
    ).length;
    const autoApprovedPct =
      data.mappings.length > 0
        ? Math.round((autoApproved / data.mappings.length) * 100)
        : 0;
    return {
      total,
      thisWeek,
      autoApprovedPct,
      golden: data.goldenRulesTotal,
    };
  }, [data]);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 p-4 text-sm text-[var(--destructive)]">
        {error}
      </div>
    );
  }

  const recent = data?.mappings.slice(0, 5) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Recent mapping activity and learned rules.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total mappings" value={stats.total} />
        <StatCard label="This week" value={stats.thisWeek} hint="last 7 days" />
        <StatCard
          label="Auto-approved %"
          value={`${stats.autoApprovedPct}%`}
          hint="of recent runs"
        />
        <StatCard label="Golden rules" value={stats.golden} />
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Recent runs</h2>
        <RecentRuns items={recent} />
      </section>
    </div>
  );
}
