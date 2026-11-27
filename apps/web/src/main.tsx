import "@fontsource-variable/inter";
import { QueryClientProvider } from "@tanstack/react-query";
import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Toaster } from "sonner";
import { App } from "./App";
import { queryClient } from "./lib/queries";
import { applyAppearance, loadAppearance, useAppearance } from "./lib/theme";
import "./styles.css";

applyAppearance(loadAppearance());

function ThemedToaster() {
  const [a] = useAppearance();
  return <Toaster position="bottom-center" theme={a.theme} richColors={false} closeButton toastOptions={{ style: { fontFamily: "var(--font)" } }} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <MotionConfig reducedMotion="user">
        <App />
        <ThemedToaster />
      </MotionConfig>
    </QueryClientProvider>
  </StrictMode>,
);

// Installable app: register the shell-only service worker in production builds.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* not fatal: the app works without it */
    });
  });
}
