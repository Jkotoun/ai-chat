import { describe, expect, it } from "vitest";
import { INTERRUPTED_ERROR, applyEvent, failIfUnfinished, newAnswer } from "./messages";

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
