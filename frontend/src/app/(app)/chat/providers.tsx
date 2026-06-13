"use client";

import "@copilotkit/react-core/v2/styles.css";

import { CopilotKit } from "@copilotkit/react-core/v2";
import { useMemo } from "react";

import { CHAT_AGENT_ID } from "@/lib/chat-constants";
import { readProjectIdFromCookie } from "@/lib/project-storage";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

/** Trailing slash avoids 307 redirect races during CopilotKit /info discovery. */
const COPILOT_RUNTIME_URL = `${BACKEND_URL}/api/v1/copilotkit/`;

/**
 * Wraps the chat in a CopilotKit provider.
 * - Authorization: session-scoped JWT for the backend
 * - X-Project-Id: active project, read from the dh_project_id cookie,
 *   so the FastAPI agent can scope all operations to the correct workspace.
 */
export function ChatProviders({
  sessionToken,
  children,
}: {
  sessionToken: string;
  children: React.ReactNode;
}) {
  const headers = useMemo(() => {
    const projectId = readProjectIdFromCookie();
    return {
      Authorization: `Bearer ${sessionToken}`,
      ...(projectId ? { "X-Project-Id": projectId } : {}),
    };
  }, [sessionToken]);

  return (
    <CopilotKit
      runtimeUrl={COPILOT_RUNTIME_URL}
      agent={CHAT_AGENT_ID}
      useSingleEndpoint
      enableInspector={false}
      headers={headers}
    >
      {children}
    </CopilotKit>
  );
}
