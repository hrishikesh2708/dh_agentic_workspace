import { ChatShell } from "@/app/(app)/chat/chat-shell";

/**
 * /chat — CopilotKit-powered mapping agent UI.
 *
 * The actual chat surface is a client component (:class:`ChatShell`) because
 * CopilotKit needs hooks + browser sessionStorage. This page just hosts it.
 */
export default function ChatPage() {
  return <ChatShell />;
}
