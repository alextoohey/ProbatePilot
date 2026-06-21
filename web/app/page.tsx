import { AlertBanner } from "@/components/AlertBanner";
import { EstateOverview } from "@/components/EstateOverview";
import { LetterPreview } from "@/components/LetterPreview";
import { TaskList } from "@/components/TaskList";
import { mockEstate } from "@/lib/mockEstate";
import type { EstateState } from "@/types/estate";

async function loadSeed(): Promise<EstateState> {
  const baseUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
  try {
    const response = await fetch(`${baseUrl}/api/agent/seed`, { method: "POST", cache: "no-store" });
    if (!response.ok) return mockEstate;
    const payload = await response.json();
    return payload.estate;
  } catch {
    return mockEstate;
  }
}

export default async function DashboardPage() {
  const estate = await loadSeed();
  const alerts = [...estate.alerts].sort((left, right) => {
    const rank = { critical: 0, warning: 1, info: 2 };
    return rank[left.severity] - rank[right.severity];
  });

  return (
    <main className="mx-auto max-w-6xl space-y-8 p-6">
      <header>
        <p className="text-sm font-semibold uppercase tracking-wide text-slate-600">Executor AI</p>
        <h1 className="mt-2 text-3xl font-semibold">Executor dashboard</h1>
      </header>
      <EstateOverview estate={estate} />
      <section className="space-y-3">
        {alerts.map((alert) => (
          <AlertBanner key={alert.id} alert={alert} />
        ))}
      </section>
      <TaskList tasks={estate.tasks} />
      <LetterPreview />
    </main>
  );
}
