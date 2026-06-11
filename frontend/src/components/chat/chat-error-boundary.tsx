"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

import { CopilotChatLayout, CopilotOfflineBanner } from "./copilot-chat-layout";

interface Props {
  children: ReactNode;
  projectName?: string;
  /** When "inline", only replace the message area — header keeps projectName. */
  mode?: "full" | "inline";
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
      const message =
        this.props.fallbackMessage ??
        `Agent connection failed (${this.state.error.message}).`;

      if (this.props.mode === "inline") {
        return (
          <CopilotOfflineBanner
            message={`${message} The chat header and project context stay available.`}
          />
        );
      }

      return (
        <CopilotChatLayout
          projectName={this.props.projectName}
          inputDisabled
          inputPlaceholder="Agent unavailable — connect backend to chat"
          banner={<CopilotOfflineBanner message={message} />}
        />
      );
    }

    return this.props.children;
  }
}
