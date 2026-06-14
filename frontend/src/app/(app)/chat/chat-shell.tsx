"use client";

import { useEffect, useState } from "react";

import { ChatProviders } from "@/app/(app)/chat/providers";
import {
  CopilotChatLayout,
  CopilotOfflineBanner,
} from "@/components/chat/copilot-chat-layout";
import { HeadlessChat } from "@/components/chat/headless-chat";
import { ProjectProvider } from "@/components/project/project-context";
import { Spinner } from "@/components/ui/spinner";
import { apiClient, ApiError } from "@/lib/api-client";
import { loadStoredProject } from "@/lib/project-storage";

/** Shape returned by POST /api/v1/auth/session */
interface SessionCreateResponse {
  session_id: string;
  name: string;
  token: {
    access_token: string;
    token_type: string;
    expires_at: number;
  };
}

const SESSION_KEY = "dh_chat_session";

interface StoredSession {
  session_id: string;
  access_token: string;
  expires_at: number;
}

function loadStoredSession(): StoredSession | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredSession;
    if (parsed.expires_at * 1000 < Date.now()) {
      window.sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function storeSession(session: StoredSession) {
  if (typeof window === "undefined") return;
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

/**
 * Bootstraps a CopilotKit session token then mounts HeadlessChat.
 * Project is guaranteed to exist by middleware (/chat redirects to /project if missing).
 */
export function ChatShell() {
  const [session, setSession] = useState<StoredSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        // DEV ONLY: skip cached session so every refresh creates a fresh thread.
        // Remove the `process.env.NODE_ENV !== "development"` guard before shipping.
        const existing =
          process.env.NODE_ENV !== "development" ? loadStoredSession() : null;
        if (existing) {
          if (!cancelled) { setSession(existing); setLoading(false); }
          return;
        }

        const created = await apiClient.post<SessionCreateResponse>("/auth/session");
        const next: StoredSession = {
          session_id: created.session_id,
          access_token: created.token.access_token,
          expires_at: created.token.expires_at,
        };
        storeSession(next);
        if (!cancelled) { setSession(next); setLoading(false); }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) return;
        setError(err instanceof Error ? err.message : "session_create_failed");
        setLoading(false);
      }
    }

    void bootstrap();
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <CopilotChatLayout
        inputDisabled
        banner={
          <div className="flex items-center gap-2">
            <Spinner size="sm" />
            Preparing chat session…
          </div>
        }
      />
    );
  }

  if (error || !session) {
    return (
      <CopilotChatLayout
        inputDisabled
        inputPlaceholder="Connect backend session to start chatting"
        banner={
          <CopilotOfflineBanner
            message={`Session could not be created (${error ?? "unknown error"}). Check that the backend is running.`}
          />
        }
      />
    );
  }

  // Project is guaranteed by middleware — loadStoredProject() will always return a value here
  const project = loadStoredProject()!;

  return (
    <ProjectProvider project={project}>
      <ChatProviders sessionToken={session.access_token}>
        <HeadlessChat
          projectName={project.name}
          sessionId={session.session_id}
        />
      </ChatProviders>
    </ProjectProvider>
  );
}
