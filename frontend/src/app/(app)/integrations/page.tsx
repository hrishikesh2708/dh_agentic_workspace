"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import type { SalesforceStatus } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

export default function IntegrationsPage() {
  const [status, setStatus] = useState<SalesforceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiClient.get<SalesforceStatus>(
          "/integrations/salesforce/status",
        );
        if (!cancelled) setStatus(data);
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
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Connect upstream data sources to feed the mapping agent.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div>
            <CardTitle>Salesforce</CardTitle>
            <CardDescription>
              OAuth2 connection used to pull Leads, Contacts, and custom
              objects.
            </CardDescription>
          </div>
          {loading ? (
            <Spinner size="sm" />
          ) : status?.connected ? (
            <Badge variant="success">Connected</Badge>
          ) : (
            <Badge variant="outline">Not connected</Badge>
          )}
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="rounded-[var(--radius)] border border-[var(--destructive)] bg-[var(--destructive)]/10 px-3 py-2 text-sm text-[var(--destructive)]">
              {error}
            </div>
          ) : null}
        </CardContent>
        <CardFooter className="justify-end">
          <Button
            disabled={loading || !status?.auth_url}
            onClick={() => {
              if (status?.auth_url) {
                window.location.href = status.auth_url;
              }
            }}
          >
            {status?.connected ? "Reconnect" : "Connect"}
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
