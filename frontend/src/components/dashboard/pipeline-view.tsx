"use client";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  MOCK_FIELD_MAPPINGS,
  MOCK_PIPELINES,
  type MockPipeline,
} from "@/lib/mock-workspace";
import { cn } from "@/lib/utils";

import { useShell } from "@/components/shell/shell-context";

function StepCard({
  title,
  subtitle,
  complete,
}: {
  title: string;
  subtitle: string;
  complete: boolean;
}) {
  return (
    <div className="relative min-w-[140px] rounded-[var(--radius)] border border-[var(--border)] bg-[var(--card)] p-4">
      {complete && (
        <span className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-[var(--success)] text-[10px] text-[var(--success-foreground)]">
          ✓
        </span>
      )}
      <div className="text-xs text-[var(--muted-foreground)]">{title}</div>
      <div className="mt-1 text-sm font-medium">{subtitle}</div>
    </div>
  );
}

function PipelineHeader({ pipeline }: { pipeline: MockPipeline }) {
  const title = `${pipeline.source} → ${pipeline.destination} CAPI`;
  const awaitingReview = pipeline.status === "review";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">{title}</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Set up by agent • {pipeline.stepsComplete} of {pipeline.stepsTotal}{" "}
            steps complete
            {awaitingReview && " • awaiting your review"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {awaitingReview && (
            <Badge variant="warning">Needs approval</Badge>
          )}
          <Button variant="outline" size="sm">
            View full config
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="text-[var(--muted-foreground)]">Agents running:</span>
        <Badge variant="success">Onboarding</Badge>
        <Button variant="outline" size="sm">
          Health monitor
        </Button>
      </div>
    </div>
  );
}

function PipelineFlow() {
  return (
    <div className="flex items-center gap-3 overflow-x-auto py-2">
      <StepCard
        title="Source"
        subtitle="Salesforce CRM"
        complete
      />
      <div className="flex items-center gap-1 text-[var(--muted-foreground)]">
        <span className="h-px w-8 bg-[var(--border)]" />
        <span className="h-2 w-2 rounded-sm border border-[var(--border)]" />
        <span className="h-px w-8 bg-[var(--border)]" />
      </div>
      <StepCard title="Auth" subtitle="OAuth verified" complete />
    </div>
  );
}

function FieldMappingApproval() {
  return (
    <div className="rounded-[var(--radius)] border border-[var(--warning)] bg-[var(--card)] p-6">
      <h2 className="text-lg font-semibold">
        Agent needs your approval — field mapping
      </h2>
      <p className="mt-2 text-sm text-[var(--muted-foreground)]">
        I mapped 6 fields from Salesforce to Meta CAPI. 2 PII fields will be
        hashed before send. &quot;Lead Source&quot; has no direct match — please
        confirm or override.
      </p>

      <div className="mt-4 overflow-x-auto rounded-[var(--radius)] border border-[var(--border)]">
        <table className="w-full min-w-[360px] text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] bg-[var(--secondary)]/50 text-left">
              <th className="px-4 py-2 font-medium">Salesforce field</th>
              <th className="px-4 py-2 font-medium">Meta CAPI field</th>
            </tr>
          </thead>
          <tbody>
            {MOCK_FIELD_MAPPINGS.map((row) => (
              <tr
                key={row.sourceField}
                className="border-b border-[var(--border)] last:border-0"
              >
                <td className="px-4 py-2">{row.sourceField}</td>
                <td
                  className={cn(
                    "px-4 py-2",
                    row.note && "text-[var(--warning)]",
                  )}
                >
                  {row.destinationField}
                  {row.note && (
                    <span className="ml-2 text-xs text-[var(--muted-foreground)]">
                      ({row.note})
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex gap-2">
        <Button>Approve mapping</Button>
        <Button variant="outline">Edit fields</Button>
      </div>
    </div>
  );
}

export function PipelineView() {
  const { selectedPipelineId } = useShell();
  const pipeline =
    MOCK_PIPELINES.find((p) => p.id === selectedPipelineId) ??
    MOCK_PIPELINES[0];

  if (!pipeline) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm text-[var(--muted-foreground)]">
          No pipelines yet. Connect an integration to get started.
        </p>
        <a
          href="/integrations"
          className="inline-flex h-9 items-center justify-center rounded-[var(--radius)] border border-[var(--border)] bg-[var(--background)] px-4 text-sm font-medium transition-colors hover:bg-[var(--secondary)]"
        >
          Add connector
        </a>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PipelineHeader pipeline={pipeline} />
      <PipelineFlow />
      {pipeline.status === "review" && <FieldMappingApproval />}
    </div>
  );
}
