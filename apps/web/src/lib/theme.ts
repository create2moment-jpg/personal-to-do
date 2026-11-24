import { useEffect, useState } from "react";

export type ThemeMode = "system" | "light" | "dark";
export type Accent = "indigo" | "violet" | "blue" | "teal" | "amber" | "rose";
export type Density = "comfortable" | "compact";
export type DisplaySize = "auto" | "compact" | "comfortable" | "large" | "xl";
export type DarkPalette = "graphite" | "obsidian" | "midnight" | "forest" | "aubergine";

/** Dark palettes: [name, description, background, surface] for previews. */
export const DARK_PALETTES: Record<DarkPalette, { label: string; hint: string; bg: string; surface: string }> = {
  graphite: { label: "Graphite", hint: "Neutral near-black (default)", bg: "#0e0e10", surface: "#161618" },
  obsidian: { label: "Obsidian", hint: "True black, ideal for OLED", bg: "#000000", surface: "#0c0c0d" },
  midnight: { label: "Midnight", hint: "Deep navy", bg: "#0b1020", surface: "#111831" },
  forest: { label: "Forest", hint: "Green-tinted night", bg: "#0b110e", surface: "#111a15" },
  aubergine: { label: "Aubergine", hint: "Deep plum", bg: "#120d16", surface: "#1a1320" },
};

export interface Appearance {
  theme: ThemeMode;
  accent: Accent;
  density: Density;
  dark: DarkPalette;
  display: DisplaySize;
}

export const ACCENTS: Record<Accent, { label: string; swatch: string }> = {
  indigo: { label: "Indigo", swatch: "#5b5bd6" },
  violet: { label: "Violet", swatch: "#7c5cdb" },
  blue: { label: "Ocean", swatch: "#2f7de1" },
  teal: { label: "Teal", swatch: "#12a594" },
  amber: { label: "Amber", swatch: "#d9822b" },
  rose: { label: "Rose", swatch: "#d6407a" },
};

const KEY = "ppos.appearance";
const DEFAULTS: Appearance = { theme: "system", accent: "indigo", density: "comfortable", dark: "graphite", display: "auto" };

// UI preferences only (per browser). Never personal content.
export function loadAppearance(): Appearance {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Appearance>) } : DEFAULTS;
  } catch {
    return DEFAULTS;
  }
}

export function applyAppearance(a: Appearance) {
  const root = document.documentElement;
  const dark = a.theme === "dark" || (a.theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  root.dataset.theme = dark ? "dark" : "light";
  root.dataset.accent = a.accent;
  root.dataset.density = a.density;
  root.dataset.dark = a.dark;
  root.dataset.display = a.display;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? DARK_PALETTES[a.dark].bg : "#f7f7f5");
}

const listeners = new Set<(a: Appearance) => void>();

export function setAppearance(a: Appearance) {
  try {
    localStorage.setItem(KEY, JSON.stringify(a));
  } catch {
    /* storage unavailable: still apply for this session */
  }
  applyAppearance(a);
  listeners.forEach((l) => l(a));
}

export function useAppearance(): [Appearance, (patch: Partial<Appearance>) => void] {
  const [value, setValue] = useState(loadAppearance);
  useEffect(() => {
    listeners.add(setValue);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => applyAppearance(loadAppearance());
    mq.addEventListener("change", onChange);
    return () => {
      listeners.delete(setValue);
      mq.removeEventListener("change", onChange);
    };
  }, []);
  return [value, (patch) => setAppearance({ ...value, ...patch })];
}
