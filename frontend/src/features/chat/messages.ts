import type { Source } from "@/client";
import type { ChatEvent } from "./api";

export type Question = { role: "user"; text: string };

export type Answer = {
  role: "assistant";
  text: string;
  sources: Source[];
  status: "streaming" | "done" | "error";
  error?: string;
};

export type Message = Question | Answer;

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
