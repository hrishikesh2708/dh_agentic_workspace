const CHAT_SESSION_KEY = "dh_chat_session";

interface StoredChatSession {
  session_id: string;
  access_token: string;
  expires_at: number;
}

/** Active chat session id from sessionStorage (set by chat-shell on bootstrap). */
export function loadStoredSessionId(): string | null {
  if (typeof window === "undefined") return null;
  const raw = window.sessionStorage.getItem(CHAT_SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as StoredChatSession;
    if (parsed.expires_at * 1000 < Date.now()) {
      window.sessionStorage.removeItem(CHAT_SESSION_KEY);
      return null;
    }
    return typeof parsed.session_id === "string" && parsed.session_id
      ? parsed.session_id
      : null;
  } catch {
    return null;
  }
}
