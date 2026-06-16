"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useAuth } from "@/hooks/use-auth";
import { cn } from "@/lib/utils";
import { readProjectIdFromCookie } from "@/lib/project-storage";

const CONNECTOR_SLUGS = ["salesforce", "meta_capi", "google_ads", "tiktok", "snapchat"] as const;
type ConnectorSlug = typeof CONNECTOR_SLUGS[number];

async function debugDeleteConnection(connectorSlug: ConnectorSlug): Promise<string> {
  const projectId = readProjectIdFromCookie();
  if (!projectId) return "No active project (set one first)";
  const res = await fetch(`/api/connections/${connectorSlug}?project_id=${projectId}`, { method: "DELETE" });
  if (res.ok) {
    const data = await res.json() as { deleted: number };
    return `Deleted ${data.deleted} row(s) for ${connectorSlug}`;
  }
  return `Error ${res.status}: ${await res.text()}`;
}

function debugAuthenticate(connectorSlug: ConnectorSlug, setMsg: (m: string) => void) {
  const projectId = readProjectIdFromCookie();
  if (!projectId) { setMsg("No active project (set one first)"); return; }

  setMsg("Opening…");
  fetch(`/api/connections/${connectorSlug}?project_id=${projectId}`, { method: "POST" })
    .then(r => r.json())
    .then((data: { auth_url?: string; detail?: string }) => {
      if (!data.auth_url) { setMsg(`Error: ${data.detail ?? "no auth_url returned"}`); return; }
      const popup = window.open(data.auth_url, "oauth_debug", "width=600,height=700");
      if (!popup) { setMsg("Popup blocked — allow popups and retry"); return; }

      function onMessage(event: MessageEvent) {
        if (event.data?.type !== "oauth_complete") return;
        window.removeEventListener("message", onMessage);
        if (event.data.success) {
          setMsg(`✓ ${connectorSlug} connected`);
        } else {
          setMsg(`✗ ${event.data.error ?? "auth failed"}`);
        }
      }
      window.addEventListener("message", onMessage);
    })
    .catch(err => setMsg(`Fetch error: ${String(err)}`));
}

export function SidebarUserFooter({ collapsed }: { collapsed: boolean }) {
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const [devOpen, setDevOpen] = useState(false);
  const [devMsg, setDevMsg] = useState<string | null>(null);

  const displayName = user?.email ?? user?.user_id + " " + "Signed in";

  async function onLogout() {
    await logout();
    router.replace("/login");
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 border-t border-[var(--border)] px-2 py-3">
        <span
          title={displayName}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--secondary)] text-xs font-medium text-[var(--secondary-foreground)]"
        >
          {loading ? "…" : displayName.charAt(0).toUpperCase()}
        </span>
        <ThemeToggle compact />
        <Button
          variant="ghost"
          size="icon"
          onClick={onLogout}
          aria-label="Sign out"
          className="h-8 w-8"
          title="Sign out"
        >
          ⎋
        </Button>
      </div>
    );
  }

  return (
    <div className="border-t border-[var(--border)] px-3 py-3">
      <div className="mb-3 min-w-0">
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Spinner size="sm" />
            Loading…
          </div>
        ) : (
          <>
            <p className="truncate text-sm font-medium text-[var(--foreground)]">
              {displayName}
            </p>
            {user?.email && user.user_id ? (
              <p className="truncate text-xs text-[var(--muted-foreground)]">
                {user.user_id}
              </p>
            ) : null}
          </>
        )}
      </div>
      <div className={cn("flex items-center gap-2")}>
        <ThemeToggle />
        <Button variant="outline" size="sm" onClick={onLogout} className="flex-1">
          Sign out
        </Button>
      </div>

      {/* ── DEV panel ─────────────────────────────────────────────────── */}
      <div className="mt-2 border-t border-dashed border-[var(--border)]/60 pt-2">
        <button
          className="w-full text-left text-[10px] font-mono text-[var(--muted-foreground)] hover:text-[var(--foreground)] transition-colors"
          onClick={() => { setDevOpen(o => !o); setDevMsg(null); }}
        >
          {devOpen ? "▾" : "▸"} [dev] connections
        </button>

        {devOpen && (
          <div className="mt-1 flex flex-col gap-0.5">
            {/* Header row */}
            <div className="grid grid-cols-[1fr_auto_auto] items-center gap-1 px-1 mb-1">
              <span className="text-[9px] font-mono text-[var(--muted-foreground)] uppercase tracking-wide">connector</span>
              <span className="text-[9px] font-mono text-[var(--muted-foreground)] uppercase tracking-wide">auth</span>
              <span className="text-[9px] font-mono text-[var(--muted-foreground)] uppercase tracking-wide">del</span>
            </div>

            {CONNECTOR_SLUGS.map(slug => (
              <div key={slug} className="grid grid-cols-[1fr_auto_auto] items-center gap-1 px-1 py-0.5 rounded hover:bg-[var(--muted)]/30">
                <span className="text-[10px] font-mono text-[var(--foreground)] truncate">{slug}</span>

                {/* Authenticate */}
                <button
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-50 text-blue-600 hover:bg-blue-100 dark:bg-blue-950 dark:text-blue-400 dark:hover:bg-blue-900 transition-colors"
                  title={`Authenticate ${slug}`}
                  onClick={() => debugAuthenticate(slug, setDevMsg)}
                >
                  ↗
                </button>

                {/* Delete */}
                <button
                  className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-50 text-red-500 hover:bg-red-100 dark:bg-red-950 dark:text-red-400 dark:hover:bg-red-900 transition-colors"
                  title={`Delete ${slug} connection`}
                  onClick={async () => {
                    setDevMsg("…");
                    setDevMsg(await debugDeleteConnection(slug));
                  }}
                >
                  ×
                </button>
              </div>
            ))}

            {devMsg && (
              <p className="text-[10px] font-mono mt-1 px-2 py-1 bg-[var(--muted)]/40 rounded text-[var(--muted-foreground)] break-all">
                {devMsg}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
