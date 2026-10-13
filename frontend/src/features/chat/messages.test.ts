import { describe, expect, it } from "vitest";
import {
  INTERRUPTED_ERROR,
  MAX_HISTORY_CONTENT_LENGTH,
  MAX_HISTORY_MESSAGES,
  applyEvent,
  failIfUnfinished,
  newAnswer,
  toHistory,
  type Answer,
  type Message,
} from "./messages";

const source = { id: 1, source: "faq", title: "Refunds", score: 0.9 };

describe("applyEvent", () => {
  it("builds the answer from sources and tokens", () => {
    let answer = applyEvent(newAnswer(), { type: "sources", sources: [source] });
    answer = applyEvent(answer, { type: "token", text: "Hel" });
    answer = applyEvent(answer, { type: "token", text: "lo" });

    expect(answer).toMatchObject({ text: "Hello", sources: [source], status: "streaming" });
  });

  it("finishes on done", () => {
    expect(applyEvent(newAnswer(), { type: "done" }).status).toBe("done");
  });

  it("keeps the server's error message", () => {
    const answer = applyEvent(newAnswer(), { type: "error", detail: "Try again." });

    expect(answer).toMatchObject({ status: "error", error: "Try again." });
  });
});

describe("failIfUnfinished", () => {
  it("fails an answer that is still streaming", () => {
    expect(failIfUnfinished(newAnswer())).toMatchObject({
      status: "error",
      error: INTERRUPTED_ERROR,
    });
  });

  it("leaves finished answers alone", () => {
    const done = applyEvent(newAnswer(), { type: "done" });

    expect(failIfUnfinished(done)).toBe(done);
  });
});

describe("toHistory", () => {
  const answer = (text: string, status: Answer["status"] = "done"): Answer => ({
    ...newAnswer(),
    text,
    status,
  });

  it("keeps questions and finished answers in order", () => {
    const messages: Message[] = [{ role: "user", text: "Hi" }, answer("Hello!")];

    expect(toHistory(messages)).toEqual([
      { role: "user", content: "Hi" },
      { role: "assistant", content: "Hello!" },
    ]);
  });

  it("leaves out failed, unfinished, and empty answers", () => {
    const messages: Message[] = [
      { role: "user", text: "Q1" },
      answer("Partial", "error"),
      { role: "user", text: "Q2" },
      answer(""),
      { role: "user", text: "Q3" },
      answer("Streaming", "streaming"),
    ];

    expect(toHistory(messages).map((message) => message.content)).toEqual(["Q1", "Q2", "Q3"]);
  });

  it("keeps only the latest messages, truncated to the backend's limits", () => {
    const messages: Message[] = Array.from({ length: MAX_HISTORY_MESSAGES + 5 }, (_, i) => ({
      role: "user",
      text: `${i}`.padEnd(MAX_HISTORY_CONTENT_LENGTH + 10, "x"),
    }));

    const history = toHistory(messages);

    expect(history).toHaveLength(MAX_HISTORY_MESSAGES);
    expect(history[0].content).toMatch(/^5x/);
    expect(history[0].content).toHaveLength(MAX_HISTORY_CONTENT_LENGTH);
  });
});
