import type { HistoryMessage, Source } from "@/client";
import type { ChatEvent } from "./api";

export type Question = { role: "user"; text: string };

export type Answer = {
  role: "assistant";
  text: string;
  sources: Source[];
  status: "streaming" | "done" | "error";
  error?: string;
  /** Set when the question was handed over to human support. */
  ticketReference?: string;
};

export type Message = Question | Answer;

// Match the backend's ChatRequest limits.
export const MAX_HISTORY_MESSAGES = 20;
export const MAX_HISTORY_CONTENT_LENGTH = 4000;

export const ESCALATION_QUESTION = "I'd like to talk to a human support agent.";

export const INTERRUPTED_ERROR = "The answer could not be completed, please try again.";

export function newAnswer(): Answer {
  return { role: "assistant", text: "", sources: [], status: "streaming" };
}

export function applyEvent(answer: Answer, event: ChatEvent): Answer {
  switch (event.type) {
    case "sources":
      return { ...answer, sources: event.sources };
    case "token":
      return { ...answer, text: answer.text + event.text };
    case "ticket":
      return { ...answer, ticketReference: event.reference };
    case "done":
      return { ...answer, status: "done" };
    case "error":
      return { ...answer, status: "error", error: event.detail };
  }
}

/** A stream that ended without `done` or `error` was cut off or never started. */
export function failIfUnfinished(answer: Answer): Answer {
  if (answer.status !== "streaming") return answer;
  return { ...answer, status: "error", error: INTERRUPTED_ERROR };
}

/** The conversation so far as context for the next question; failed answers are left out. */
export function toHistory(messages: Message[]): HistoryMessage[] {
  return messages
    .filter((message) => message.role === "user" || message.status === "done")
    .map((message) => ({
      role: message.role,
      content: message.text.slice(0, MAX_HISTORY_CONTENT_LENGTH),
    }))
    .filter((message) => message.content.trim())
    .slice(-MAX_HISTORY_MESSAGES);
}
