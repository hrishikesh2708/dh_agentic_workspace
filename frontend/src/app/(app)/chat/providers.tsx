"use client";

import "@copilotkit/react-core/v2/styles.css";

import { HttpAgent } from "@ag-ui/client";
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
 * We pre-register an {@link HttpAgent} so CopilotKit does not throw
 * "agent not found" during the brief window before /info discovery completes.
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

  const agents = useMemo(
    () => ({
      [CHAT_AGENT_ID]: new HttpAgent({
        url: COPILOT_RUNTIME_URL,
        headers: authHeaders,
      }),
    }),
    [authHeaders],
  );

  return (
    <CopilotKit
      runtimeUrl={COPILOT_RUNTIME_URL}
      agent={CHAT_AGENT_ID}
      useSingleEndpoint
      enableInspector={false}
      headers={authHeaders}
      agents__unsafe_dev_only={agents}
    >
      {children}
    </CopilotKit>
  );
}
