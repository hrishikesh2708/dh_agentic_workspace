"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MOCK_CONNECTORS } from "@/lib/mock-workspace";

const AVAILABLE_INTEGRATIONS = [
  {
    id: "salesforce",
    name: "Salesforce",
    description:
      "OAuth2 connection used to pull Leads, Contacts, and custom objects.",
  },
  {
    id: "meta",
    name: "Meta",
    description: "Conversions API destination for ad platform event matching.",
  },
  {
    id: "zoho",
    name: "Zoho",
    description: "CRM source for leads and contact synchronization.",
  },
  {
    id: "tiktok",
    name: "TikTok",
    description: "Events API destination for TikTok ad optimization.",
  },
];

export default function IntegrationsPage() {
  const connectedIds = new Set(
    MOCK_CONNECTORS.filter((c) => c.authenticated).map((c) => c.id),
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Integrations</h1>
        <p className="text-sm text-[var(--muted-foreground)]">
          Connectors authenticated for this workspace.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {AVAILABLE_INTEGRATIONS.map((integration) => {
          const connected = connectedIds.has(integration.id);
          return (
            <Card key={integration.id}>
              <CardHeader className="flex flex-row items-start justify-between">
                <div>
                  <CardTitle>{integration.name}</CardTitle>
                  <CardDescription>{integration.description}</CardDescription>
                </div>
                {connected ? (
                  <Badge variant="success">Connected</Badge>
                ) : (
                  <Badge variant="outline">Not connected</Badge>
                )}
              </CardHeader>
              <CardFooter className="justify-end">
                <Button variant={connected ? "outline" : "default"} disabled>
                  {connected ? "Manage" : "Connect"}
                </Button>
              </CardFooter>
            </Card>
          );
        })}
      </div>

      {MOCK_CONNECTORS.filter((c) => c.authenticated).length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Authenticated connectors</h2>
          <div className="flex flex-wrap gap-2">
            {MOCK_CONNECTORS.filter((c) => c.authenticated).map((connector) => (
              <div
                key={connector.id}
                className="flex items-center gap-2 rounded-[var(--radius)] border border-[var(--border)] px-3 py-2 text-sm"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded border border-[var(--border)] text-xs font-semibold">
                  {connector.icon}
                </span>
                {connector.name}
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
