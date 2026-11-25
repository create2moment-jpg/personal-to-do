import { describe, expect, it } from "vitest";
import { parseDuration, splitEstimate } from "./util";

describe("parseDuration", () => {
  it.each([
    ["50", 50],
    ["7", 7],
    ["50m", 50],
    ["90min", 90],
    ["1h", 60],
    ["1h20", 80],
    ["1h 20m", 80],
    ["1.5h", 90],
    ["1,5h", 90],
    ["1:30", 90],
    ["~45m", 45],
  ])("%s → %d", (input, minutes) => expect(parseDuration(input)).toBe(minutes));
  it.each(["", "abc", "0", "25h", "1h99x"])("rejects %s", (input) => expect(parseDuration(input)).toBeNull());
});

describe("splitEstimate", () => {
  it("takes a trailing ~duration as the estimate", () => {
    expect(splitEstimate("Write spec ~50m")).toEqual({ title: "Write spec", minutes: 50 });
    expect(splitEstimate("Review ~1h30")).toEqual({ title: "Review", minutes: 90 });
    expect(splitEstimate("Plain title")).toEqual({ title: "Plain title", minutes: null });
    expect(splitEstimate("Version ~two")).toEqual({ title: "Version ~two", minutes: null });
  });
});
