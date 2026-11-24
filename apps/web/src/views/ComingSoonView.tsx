import { motion } from "framer-motion";
import {
  BarChart3,
  Brain,
  CalendarRange,
  FileSearch,
  FileText,
  GitBranch,
  Gauge,
  Layers,
  LineChart,
  Lock,
  type LucideIcon,
  MessageSquareText,
  Quote,
  Rocket,
  ScrollText,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Wand2,
} from "lucide-react";
import { ALL_NAV } from "../lib/nav";
import type { ViewId } from "../lib/ui-store";

interface Preview {
  tagline: string;
  description: string;
  features: { icon: LucideIcon; title: string; text: string }[];
}

const PREVIEWS: Partial<Record<ViewId, Preview>> = {
  week: {
    tagline: "See the whole week, commit with intent",
    description: "Seven day columns with meetings, capacity and objectives, and your sprint backlog alongside — drag work into the day it belongs.",
    features: [
      { icon: CalendarRange, title: "Week board", text: "Plan across days with per-day capacity and overcommitment warnings." },
      { icon: Target, title: "Weekly objectives", text: "Three outcomes for the week, linked to the tasks that deliver them." },
      { icon: ScrollText, title: "Weekly review", text: "Done vs. planned, rollover, lessons and risks — pre-filled from your records." },
    ],
  },
  sprint: {
    tagline: "2–3 week sprints for one",
    description: "A sprint goal, committed and stretch work, and an honest review of commitment versus completion.",
    features: [
      { icon: Rocket, title: "Sprint goal & scope", text: "Committed vs. stretch work, with scope changes tracked automatically." },
      { icon: Gauge, title: "Burndown", text: "See early whether the sprint is on track." },
      { icon: LineChart, title: "Sprint review", text: "Completion rate, rollover causes and next-sprint recommendations." },
    ],
  },
  knowledge: {
    tagline: "Your documents, searchable and cited",
    description: "Drop in performance reports, frameworks and technical documents. Every extracted fact keeps a link to its page and paragraph.",
    features: [
      { icon: FileSearch, title: "Private ingestion", text: "Extraction and OCR run locally; originals are preserved and versioned." },
      { icon: Quote, title: "Provenance everywhere", text: "Each fact cites document, page, extractor version and confidence." },
      { icon: Layers, title: "Hybrid search", text: "Keyword + semantic retrieval over everything you’ve written and stored." },
    ],
  },
  ai: {
    tagline: "An assistant that never leaves your machine",
    description: "A local model (Ollama / vLLM) drafts plans, rewrites text and summarises your week — always as a proposal you review.",
    features: [
      { icon: Wand2, title: "Writing studio", text: "Rough notes → crisp email, update or technical note. Originals are never overwritten." },
      { icon: MessageSquareText, title: "Grounded answers", text: "Answers cite the tasks, notes and documents they came from." },
      { icon: ShieldCheck, title: "You approve changes", text: "AI suggestions are audited and only applied with your consent." },
    ],
  },
  goals: {
    tagline: "From vision to today’s task",
    description: "Yearly → quarterly → sprint → weekly → daily, with alignment you can actually see.",
    features: [
      { icon: Target, title: "Goal hierarchy", text: "Measurable and qualitative goals with confidence and deadlines." },
      { icon: GitBranch, title: "Alignment", text: "Spot strategic goals with no active work, and busywork with no goal." },
      { icon: TrendingUp, title: "Trajectory", text: "Are you on pace? Evidence-based progress over time." },
    ],
  },
  skills: {
    tagline: "Evidence-backed career growth",
    description: "Map your work to competencies and levels from your own framework — with sources, never invented achievements.",
    features: [
      { icon: Brain, title: "Competency matrix", text: "Levels, dimensions and expectations, normalised from your documents." },
      { icon: Quote, title: "Evidence with provenance", text: "Documented, self-reported and inferred evidence kept clearly apart." },
      { icon: Sparkles, title: "Next steps", text: "Gaps and concrete actions that would generate the missing evidence." },
    ],
  },
  reviews: {
    tagline: "Reviews that write their first draft",
    description: "Weekly, monthly, bi-monthly, quarterly and annual reviews assembled from what actually happened.",
    features: [
      { icon: FileText, title: "Year-end review", text: "Assembled from twelve months of records, every claim linked to its source." },
      { icon: ScrollText, title: "Bi-monthly career check", text: "Progress against your framework, gaps and next actions." },
      { icon: Lock, title: "Private by design", text: "Generated locally; nothing is sent anywhere." },
    ],
  },
  analytics: {
    tagline: "Outcomes, not activity",
    description: "Strategic-work ratio, estimate accuracy, recurring blockers and goal momentum.",
    features: [
      { icon: BarChart3, title: "Focus mix", text: "How much time went to strategic vs. reactive work." },
      { icon: Gauge, title: "Estimation accuracy", text: "Estimate vs. actual, so plans get more realistic." },
      { icon: LineChart, title: "Trends", text: "Weeks and months compared at a glance." },
    ],
  },
};

export function ComingSoonView({ view }: { view: ViewId }) {
  const nav = ALL_NAV.find((n) => n.id === view)!;
  const p = PREVIEWS[view];
  const Icon = nav.icon;
  return (
    <div className="page">
      <motion.div className="soon-hero" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div className="project-icon" style={{ background: "var(--accent)", width: 36, height: 36, borderRadius: 10 }}>
            <Icon size={18} />
          </div>
          <span className="chip accent">Coming in {nav.phase}</span>
        </div>
        <h2>{p?.tagline ?? nav.label}</h2>
        <p>{p?.description}</p>
      </motion.div>
      <div className="soon-features">
        {p?.features.map((f, i) => (
          <motion.div key={f.title} className="card soon-feature" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 * (i + 1) }}>
            <div className="f-icon">
              <f.icon />
            </div>
            <h4>{f.title}</h4>
            <p>{f.text}</p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
