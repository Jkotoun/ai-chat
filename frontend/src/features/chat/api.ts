import { chat, type HistoryMessage } from "@/client";
import { client } from "@/client/client.gen";

export type { ChatResponse as ChatEvent } from "@/client";

client.setConfig({ baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000" });

/** Streams the answer to `question`. A failed request ends the stream without a `done` event. */
export async function streamAnswer(question: string, history: HistoryMessage[]) {
  const { stream } = await chat({
    body: { question, history },
    // A retry would ask the question again.
    sseMaxRetryAttempts: 1,
    onSseError: (error) => console.error("Chat request failed", error),
  });
  return stream;
}
