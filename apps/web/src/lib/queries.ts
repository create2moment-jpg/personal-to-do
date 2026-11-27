import { QueryClient, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "./api";
import type { Note, NoteKind, Task, TaskStatus, Today } from "./types";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 15_000, refetchOnWindowFocus: true, retry: 1 },
    mutations: {
      onError: (e) => toast.error((e as Error).message),
    },
  },
});

export const keys = {
  today: (day: string) => ["today", day] as const,
  tasks: (params: object) => ["tasks", params] as const,
  task: (id: string) => ["task", id] as const,
  notes: (kind?: NoteKind) => ["notes", kind ?? "all"] as const,
  note: (id: string) => ["note", id] as const,
  versions: (id: string) => ["versions", id] as const,
  projects: ["projects"] as const,
  health: ["health"] as const,
};

/** Anything that changes tasks invalidates every task-shaped view. */
export function invalidateTasks(qc: QueryClient = queryClient) {
  for (const k of ["today", "tasks", "task", "week", "sprint", "sprints", "timeline"]) void qc.invalidateQueries({ queryKey: [k] });
}

/** Meetings affect capacity, so they refresh day/week views too. */
export function invalidateTime(qc: QueryClient = queryClient) {
  for (const k of ["today", "week", "meetings", "series", "insights", "people", "topics", "timeline"]) void qc.invalidateQueries({ queryKey: [k] });
}

export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: api.settings, staleTime: 5 * 60_000 });
export const useWeek = (day: string) => useQuery({ queryKey: ["week", day], queryFn: () => api.week(day) });
export const useSprints = () => useQuery({ queryKey: ["sprints"], queryFn: api.sprints });
export const useSprintSummary = (id: string | undefined) =>
  useQuery({ queryKey: ["sprint", id], queryFn: () => api.sprintSummary(id!), enabled: !!id });
export const useMeetings = (start: string, end: string) =>
  useQuery({ queryKey: ["meetings", start, end], queryFn: () => api.meetings(start, end) });
export const useSeries = () => useQuery({ queryKey: ["series"], queryFn: api.meetingSeries });
export const useInsights = (days: number) => useQuery({ queryKey: ["insights", days], queryFn: () => api.insights(days) });
export const usePeople = () => useQuery({ queryKey: ["people"], queryFn: api.people });
export const useTopics = () => useQuery({ queryKey: ["topics"], queryFn: api.topics });

export const useToday = (day: string) => useQuery({ queryKey: keys.today(day), queryFn: () => api.today(day) });
export const useHealth = () => useQuery({ queryKey: keys.health, queryFn: api.health, staleTime: 60_000 });
export const useProjects = () => useQuery({ queryKey: keys.projects, queryFn: api.projects });
export const useTask = (id: string) => useQuery({ queryKey: keys.task(id), queryFn: () => api.task(id) });

export function useTasks(params: Parameters<typeof api.tasks>[0]) {
  return useQuery({ queryKey: keys.tasks(params ?? {}), queryFn: () => api.tasks(params) });
}

export const useNotes = (kind?: NoteKind) =>
  useQuery({ queryKey: keys.notes(kind), queryFn: () => api.notes(kind ? { kind } : {}) });

export interface MoveArgs {
  id: string;
  status?: TaskStatus;
  scheduled_date?: string;
  unschedule?: boolean;
  position?: number;
}

/**
 * Optimistic task move: the board updates instantly, the server confirms,
 * and on failure the previous snapshot is restored.
 */
export function useMoveTask(day?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...move }: MoveArgs) => api.moveTask(id, move),
    onMutate: async (args) => {
      if (!day) return undefined;
      await qc.cancelQueries({ queryKey: keys.today(day) });
      const previous = qc.getQueryData<Today>(keys.today(day));
      if (previous) {
        const patch = (t: Task): Task =>
          t.id === args.id
            ? {
                ...t,
                status: args.status ?? t.status,
                position: args.position ?? t.position,
                scheduled_date: args.unschedule ? null : (args.scheduled_date ?? t.scheduled_date),
                completed_at: args.status === "done" ? new Date().toISOString() : args.status ? null : t.completed_at,
              }
            : t;
        const inToday = previous.tasks.some((t) => t.id === args.id);
        let tasks = previous.tasks.map(patch);
        if (!inToday && args.scheduled_date === day) {
          const source = qc
            .getQueriesData<Task[]>({ queryKey: ["tasks"] })
            .flatMap(([, list]) => list ?? [])
            .find((t) => t.id === args.id);
          if (source) tasks = [...tasks, patch(source)];
        }
        if (args.unschedule || (args.scheduled_date && args.scheduled_date !== day)) {
          tasks = tasks.filter((t) => t.id !== args.id);
        }
        qc.setQueryData<Today>(keys.today(day), { ...previous, tasks });
      }
      return { previous };
    },
    onError: (e, _args, ctx) => {
      if (day && ctx?.previous) qc.setQueryData(keys.today(day), ctx.previous);
      toast.error((e as Error).message);
    },
    onSettled: () => invalidateTasks(qc),
  });
}

export function useUpdateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, changes }: { id: string; changes: Partial<Task> }) => api.updateTask(id, changes),
    onSuccess: (task) => {
      qc.setQueryData(keys.task(task.id), task);
      invalidateTasks(qc);
    },
  });
}

export function useCreateTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<Task> & { title: string }) => api.createTask(data),
    onSuccess: () => invalidateTasks(qc),
  });
}

export function useUpdateNote(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (changes: Partial<Note> & { snapshot?: boolean }) => api.updateNote(id, changes),
    onSuccess: (note) => {
      qc.setQueryData(keys.note(id), note);
      void qc.invalidateQueries({ queryKey: ["notes"] });
      void qc.invalidateQueries({ queryKey: keys.versions(id) });
    },
  });
}
