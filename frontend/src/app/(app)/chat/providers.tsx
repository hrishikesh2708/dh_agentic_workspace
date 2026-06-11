"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotKit } from "@copilotkit/react-core/v2";

import { CHAT_AGENT_ID } from "@/lib/chat-constants";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/**
 * Wraps a chat surface in a CopilotKit provider configured to talk to the
 * datahash FastAPI backend's `/api/v1/copilotkit` AG-UI endpoint.
 *
 * The session-scoped JWT is passed via the `Authorization` header on every
 * runtime call. The agent name **must** match the backend's
 * `LangGraphAGUIAgent(name="datahash_agent", ...)` registration.
 */
export function ChatProviders({
  sessionToken,
  children,
}: {
  sessionToken: string;
  children: React.ReactNode;
}) {
  return (
    <CopilotKit
      runtimeUrl={`${BACKEND_URL}/api/v1/copilotkit`}
      agent={CHAT_AGENT_ID}
      useSingleEndpoint
      enableInspector={false}
      headers={{ Authorization: `Bearer ${sessionToken}` }}
    >
      {children}
    </CopilotKit>
  );
}
