"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotKit } from "@copilotkit/react-core/v2";
import { useMemo } from "react";

import { CHAT_AGENT_ID } from "@/lib/chat-constants";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Trailing slash avoids 307 redirect races during CopilotKit /info discovery. */
const COPILOT_RUNTIME_URL = `${BACKEND_URL}/api/v1/copilotkit/`;

/**
 * Wraps a chat surface in a CopilotKit provider configured to talk to the
 * datahash FastAPI backend's `/api/v1/copilotkit` AG-UI endpoint.
 *
 * The session-scoped JWT is passed via the `Authorization` header on every
 * runtime call. The agent name **must** match the backend's
 * `LangGraphAGUIAgent(name="datahash_agent", ...)` registration.
 *
 * Runtime discovery registers a single {@link ProxiedCopilotRuntimeAgent}
 * so every turn (including HITL resume) reuses the same thread/checkpoint.
 */
export function ChatProviders({
  sessionToken,
  children,
}: {
  sessionToken: string;
  children: React.ReactNode;
}) {
  const authHeaders = useMemo(
    () => ({ Authorization: `Bearer ${sessionToken}` }),
    [sessionToken],
  );

  return (
    <CopilotKit
      runtimeUrl={COPILOT_RUNTIME_URL}
      agent={CHAT_AGENT_ID}
      useSingleEndpoint
      enableInspector={false}
      headers={authHeaders}
    >
      {children}
    </CopilotKit>
  );
}
