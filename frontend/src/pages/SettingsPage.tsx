import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { CheckCircle2, XCircle, Loader2 } from "lucide-react";

import { PageHeader } from "../components/PageHeader";

import { API_BASE_URL as API_BASE } from "@/lib/apiBaseUrl";

interface HealthState {
  loading: boolean;
  error: string | null;
  components: Record<string, boolean> | null;
}

function StatusRow({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between border-b border-border py-2 last:border-0">
      <span className="text-sm text-foreground/90">{label}</span>
      {ok ? (
        <span className="flex items-center gap-1.5 text-sm text-positive">
          <CheckCircle2 className="h-4 w-4" /> healthy
        </span>
      ) : (
        <span className="flex items-center gap-1.5 text-sm text-destructive">
          <XCircle className="h-4 w-4" /> unavailable
        </span>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="elev rounded-xl border border-border bg-card p-5">
      <h2 className="mb-3 text-sm font-semibold text-foreground">{title}</h2>
      {children}
    </section>
  );
}

export function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const [health, setHealth] = useState<HealthState>({ loading: true, error: null, components: null });

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/health`)
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        const components = data?.components ?? {};
        const normalized: Record<string, boolean> = {};
        Object.keys(components).forEach((k) => {
          const v = components[k];
          normalized[k] = typeof v === "boolean" ? v : Boolean(v?.healthy ?? v?.status === "healthy");
        });
        setHealth({ loading: false, error: null, components: normalized });
      })
      .catch((err) => {
        if (!cancelled) setHealth({ loading: false, error: String(err), components: null });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex h-full flex-col">
      <PageHeader title="Settings" description="Appearance and backend status." />
      <div className="min-h-0 flex-1 overflow-y-auto p-6">
        <div className="stagger mx-auto grid max-w-2xl gap-5">
          <Section title="Appearance">
            <p className="mb-3 text-sm text-muted-foreground">
              dogma ships dark-first. Light theme is in progress.
            </p>
            <div className="elev-sm inline-flex gap-1 rounded-lg border border-border bg-surface-1 p-1">
              {(["dark", "light", "system"] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTheme(t)}
                  className={`rounded-md px-3 py-1.5 text-sm capitalize transition-colors active:scale-[0.98] ${
                    theme === t
                      ? "bg-primary text-primary-foreground"
                      : "text-muted-foreground hover:bg-accent hover:text-foreground"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Backend status">
            {health.loading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Checking…
              </div>
            ) : health.error ? (
              <p className="text-sm text-destructive">Could not reach the API at {API_BASE}.</p>
            ) : health.components && Object.keys(health.components).length > 0 ? (
              <div>
                {Object.entries(health.components).map(([k, ok]) => (
                  <StatusRow key={k} label={k} ok={ok} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No component status reported.</p>
            )}
          </Section>

          <Section title="Search preferences">
            <p className="text-sm text-muted-foreground">
              Organism, platform, and disease-area preferences are learned from your activity in
              Chat and applied to dataset search. Full preference management lands in a later slice.
            </p>
          </Section>
        </div>
      </div>
    </div>
  );
}
