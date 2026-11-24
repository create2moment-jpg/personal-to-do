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
