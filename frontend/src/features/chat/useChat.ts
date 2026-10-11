import { useState } from "react";
import { streamAnswer } from "./api";
import { applyEvent, failIfUnfinished, newAnswer, type Answer, type Message } from "./messages";

export function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const lastMessage = messages.at(-1);
  const isAnswering = lastMessage?.role === "assistant" && lastMessage.status === "streaming";

  /** Updates the answer being streamed, which is always the last message. */
  function updateAnswer(update: (answer: Answer) => Answer) {
    setMessages((prev) => {
      const answer = prev.at(-1);
      if (answer?.role !== "assistant") return prev;
      return [...prev.slice(0, -1), update(answer)];
    });
  }

  async function ask(question: string) {
    if (isAnswering) return;
    setMessages((prev) => [...prev, { role: "user", text: question }, newAnswer()]);
    try {
      for await (const event of await streamAnswer(question)) {
        updateAnswer((answer) => applyEvent(answer, event));
      }
    } finally {
      updateAnswer(failIfUnfinished);
    }
  }

  return { messages, isAnswering, ask };
}
