import { describe, expect, it } from "vitest";
import { findTask, parseCommand, resolveDay } from "./commands";

const FRI = new Date(2026, 10, 27); // Friday 27 Nov 2026
const tasks = [
  { id: "1", title: "Write the ADR", status: "planned" },
  { id: "2", title: "Review PR #482", status: "in_progress" },
  { id: "3", title: "Write the ADR draft", status: "done" },
];

describe("commands", () => {
  it("resolves days", () => {
    expect(resolveDay("today", FRI)).toBe("2026-11-27");
    expect(resolveDay("tomorrow", FRI)).toBe("2026-11-28");
    expect(resolveDay("mon", FRI)).toBe("2026-11-30");
    expect(resolveDay("friday", FRI)).toBe("2026-12-04"); // the next one, not today
    expect(resolveDay("next week", FRI)).toBe("2026-11-30");
    expect(resolveDay("someday", FRI)).toBeNull();
  });

  it("finds open tasks only, best match first", () => {
    expect(findTask("write", tasks)?.id).toBe("1");
    expect(findTask("pr #482", tasks)?.id).toBe("2");
    expect(findTask("x", tasks)).toBeNull();
  });

  it("parses actions", () => {
    expect(parseCommand("done write the adr", tasks, FRI)).toMatchObject({ kind: "done", task: { id: "1" } });
    expect(parseCommand("move review to monday", tasks, FRI)).toMatchObject({ kind: "move", day: "2026-11-30" });
    expect(parseCommand("timebox Review at 9:30 tomorrow", tasks, FRI)).toMatchObject({ kind: "timebox", start: "09:30", day: "2026-11-28" });
    expect(parseCommand("new note Retro ideas", tasks, FRI)).toMatchObject({ kind: "note", title: "Retro ideas" });
    expect(parseCommand("board Q1 plan", tasks, FRI)).toMatchObject({ kind: "board", title: "Q1 plan" });
    expect(parseCommand("call with Priya 20m #hiring", tasks, FRI)).toMatchObject({ kind: "call", line: "call: Priya 20m #hiring" });
    expect(parseCommand("add Book flights @fri", tasks, FRI)).toMatchObject({ kind: "capture", line: "Book flights @fri" });
    expect(parseCommand("done nothing like this", tasks, FRI)).toBeNull();
    expect(parseCommand("hybrid retrieval", tasks, FRI)).toBeNull(); // plain search
  });
});
