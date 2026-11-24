import { describe, expect, it, vi } from "vitest";
import { addDays, debounce, formatMinutes } from "./util";

describe("util", () => {
  it("formats minutes", () => {
    expect(formatMinutes(null)).toBe("–");
    expect(formatMinutes(45)).toBe("45m");
    expect(formatMinutes(120)).toBe("2h");
    expect(formatMinutes(90)).toBe("1h 30m");
  });

  it("adds days across month boundaries", () => {
    expect(addDays("2026-11-30", 1)).toBe("2026-12-01");
    expect(addDays("2026-03-01", -1)).toBe("2026-02-28");
  });

  it("debounce flush runs the pending call exactly once", () => {
    vi.useFakeTimers();
    const fn = vi.fn();
    const d = debounce(fn, 100);
    d("a");
    d("b");
    d.flush();
    vi.advanceTimersByTime(200);
    expect(fn).toHaveBeenCalledTimes(1);
    expect(fn).toHaveBeenCalledWith("b");
    vi.useRealTimers();
  });
});

describe("ordering and labels", () => {
  it("computes midpoint positions", async () => {
    const { positionBetween } = await import("./util");
    expect(positionBetween(undefined, undefined)).toBe(1);
    expect(positionBetween(1, 2)).toBe(1.5);
    expect(positionBetween(undefined, 3)).toBe(2);
    expect(positionBetween(4, undefined)).toBe(5);
  });

  it("labels relative days", async () => {
    const { relativeDay } = await import("./util");
    expect(relativeDay("2026-11-24", "2026-11-24")).toBe("Today");
    expect(relativeDay("2026-11-25", "2026-11-24")).toBe("Tomorrow");
    expect(relativeDay("2026-11-23", "2026-11-24")).toBe("Yesterday");
  });
});

describe("workspace time zone", () => {
  it("computes dates, mondays and zoned instants", async () => {
    const u = await import("./util");
    u.setWorkspaceTimeZone("Europe/Berlin");
    expect(u.isoDay(new Date("2026-11-24T23:30:00Z"))).toBe("2026-11-25"); // already Wednesday in Berlin
    expect(u.mondayOf("2026-11-26")).toBe("2026-11-23");
    expect(u.zonedInstant("2026-11-24", "09:00")).toBe("2026-11-24T08:00:00.000Z"); // CET = UTC+1
    expect(u.zonedInstant("2026-07-01", "09:00")).toBe("2026-07-01T07:00:00.000Z"); // CEST = UTC+2
    u.setWorkspaceTimeZone(undefined);
  });
});
