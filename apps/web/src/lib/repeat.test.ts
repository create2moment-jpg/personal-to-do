import { describe, expect, it } from "vitest";
import { describeRepeat, parseRepeat, toRule } from "./repeat";

describe("repeat rules", () => {
  it("round-trips the server's canonical form", () => {
    for (const rule of ["FREQ=DAILY", "FREQ=WEEKLY;BYDAY=MO,TH", "FREQ=WEEKLY;INTERVAL=2", "FREQ=MONTHLY;INTERVAL=3"]) {
      expect(toRule(parseRepeat(rule))).toBe(rule);
    }
    expect(parseRepeat("")).toBeNull();
    expect(toRule(null)).toBeNull();
  });
  it("describes rules like the server", () => {
    expect(describeRepeat("FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR")).toBe("Every weekday");
    expect(describeRepeat("FREQ=WEEKLY;BYDAY=TH,MO")).toBe("Weekly on Mon, Thu");
    expect(describeRepeat("FREQ=WEEKLY;INTERVAL=2")).toBe("Every 2 weeks");
    expect(describeRepeat("FREQ=DAILY")).toBe("Daily");
  });
});
