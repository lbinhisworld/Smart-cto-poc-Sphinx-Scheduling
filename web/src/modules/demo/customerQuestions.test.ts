import { describe, expect, it } from "vitest";
import { CUSTOMER_QUESTIONS } from "./customerQuestions";

describe("customer confirmation questions", () => {
  it("keeps a closed list of still-open questions", () => {
    expect(CUSTOMER_QUESTIONS.map((q) => q.id)).toEqual([
      "Q1",
      "Q2",
      "Q3",
      "Q4",
      "Q5",
      "Q6",
      "Q7",
      "Q8",
      "Q9",
      "Q10",
      "Q11",
      "Q12",
      "Q13",
    ]);
    for (const q of CUSTOMER_QUESTIONS) {
      expect(q.ask.length).toBeGreaterThan(0);
      expect(q.question.length).toBeGreaterThan(8);
      expect(q.now.length).toBeGreaterThan(4);
      expect(q.after.length).toBeGreaterThan(4);
    }
  });
});
