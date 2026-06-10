"use client";

import { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";
import { useAgent, useCopilotKit } from "@copilotkit/react-core/v2";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

export { normalizeInterruptPayload } from "@/lib/normalize-interrupt-payload";

export const INTERRUPT_EVENT_NAME = "on_interrupt";

export type MappingField = {
  source_field: string;
  destination_field?: string | null;
  confidence: number;
  reasoning?: string;
  transformation_needed?: string | null;
  validation_status?: string;
  validation_notes?: string[];
  status?: string;
};

export type SelectOption = {
  id: string;
  label: string;
  enabled?: boolean;
  description?: string;
};

export type DestinationFieldOption = {
  name: string;
  label?: string;
  type?: string;
  required?: boolean;
  description?: string;
};

export type MappingSummary = {
  total_source_fields: number;
  mapped: number;
  not_proposed: number;
  needs_review: number;
};

export type ApprovalInterruptPayload = {
  type?: string;
  phase?: string;
  title?: string;
  message?: string;
  hint?: string;
  default_selected?: string;
  // generic approval
  proposal?: string;
  // mapping_review
  mapping_kind?: string;
  source_object?: string;
  destination_type?: string;
  destination_label?: string;
  mappings?: MappingField[];
  destination_fields?: DestinationFieldOption[];
  mapping_summary?: MappingSummary;
  // select_source | select_destination
  options?: SelectOption[] | string[];
  // select_object
  requested?: string;
};

export type InterruptEvent = {
  name: string;
  value: ApprovalInterruptPayload;
};

export function useHeadlessInterrupt() {
  const { copilotkit } = useCopilotKit();
  const { agent } = useAgent();
  const [pending, setPending] = useState<InterruptEvent | null>(null);
  const stagedRef = useRef<InterruptEvent | null>(null);
  const rawInterruptRef = useRef<unknown>(null);

  useEffect(() => {
    const sub = agent.subscribe({
      onCustomEvent: ({ event }) => {
        if (event.name === INTERRUPT_EVENT_NAME) {
          rawInterruptRef.current = event.value;
          stagedRef.current = {
            name: event.name,
            value: normalizeInterruptPayload(event.value),
          };
        }
      },
      onRunStartedEvent: () => {
        stagedRef.current = null;
        rawInterruptRef.current = null;
        setPending(null);
      },
      onRunFinalized: () => {
        if (stagedRef.current) {
          setPending(stagedRef.current);
          stagedRef.current = null;
        }
      },
      onRunFailed: () => {
        stagedRef.current = null;
        rawInterruptRef.current = null;
      },
    });
    return () => sub.unsubscribe();
  }, [agent]);

  const clear = useCallback(() => {
    stagedRef.current = null;
    rawInterruptRef.current = null;
    setPending(null);
  }, []);

  const resolve = useCallback(
    (response: unknown) => {
      const snapshot = pending;
      setPending(null);
      void copilotkit
        .runAgent({
          agent,
          forwardedProps: {
            command: {
              resume: response,
              interruptEvent: rawInterruptRef.current ?? snapshot?.value,
            },
          },
        })
        .catch(() => {});
    },
    [agent, copilotkit, pending],
  );

  return useMemo(
    () => ({ pending, resolve, clear }),
    [pending, resolve, clear],
  );
}
