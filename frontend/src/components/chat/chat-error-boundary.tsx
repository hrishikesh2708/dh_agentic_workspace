"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { CopilotChatLayout, CopilotOfflineBanner } from "./copilot-chat-layout";

interface Props {
  children: ReactNode;
  fallbackMessage?: string;
}

interface State {
  error: Error | null;
}

export class ChatErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[chat] runtime error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <CopilotChatLayout
          inputDisabled
          inputPlaceholder="Agent unavailable — connect backend to chat"
          banner={
            <CopilotOfflineBanner
              message={`Agent connection failed (${this.state.error.message}). The UI shell is shown so you can keep building the chat experience.`}
            />
          }
        />
      );
    }

    return this.props.children;
  }
}
