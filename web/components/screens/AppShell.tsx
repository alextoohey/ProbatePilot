"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { ExecutorIcons } from "@/lib/design/icons";
import {
  DEMO_ESTATE,
  EXECUTOR_PROFILE,
  type EstateProfile,
  type ExecutorProfile,
  type Alert as DesignAlert,
} from "@/lib/design/data";
import { completeAlert, getMe, logout as apiLogout, runDeadlineAgent, getEstate } from "@/lib/agentClient";
import type { Alert as BackendAlert, EstateState, PublicUser } from "@/types";
import { Sidebar } from "./Sidebar";
import { DashboardScreen } from "./DashboardScreen";
import { StepDetailScreen } from "./StepDetailScreen";
import { ChatScreen } from "./ChatScreen";
import { UploadScreen } from "./UploadScreen";
import { LettersScreen } from "./LettersScreen";
import { NotificationsMenu } from "./NotificationsMenu";
import { CreateEstateModal } from "./CreateEstateModal";
import { ProfileEditorModal } from "./ProfileEditorModal";

type Route = "dashboard" | "documents" | "chat" | "letters";
type NotifPrefs = { all: boolean; deadlines: boolean; weekly: boolean; email: boolean };
function fallbackSteps(alert: BackendAlert): string[] {
  return [
    `Confirm the current status of ${alert.title.toLowerCase()} and gather any supporting document or note that shows what has already been done.`,
    alert.actionRequired.endsWith(".") ? alert.actionRequired : `${alert.actionRequired}.`,
    "Update the estate record so this alert and its linked task clear on the next refresh.",
  ];
}

function fallbackWhatYouNeed(alert: BackendAlert): string[] {
  return [
    "The current status of this filing, notice, or task",
    "Any supporting document that proves the step is complete",
    "The date to record once the estate file has been updated",
  ];
}

function toDisplayAlert(alert: BackendAlert, guidanceAlerts: DesignAlert[]): DesignAlert {
  const guidance = guidanceAlerts.find((item) => item.id === alert.id);
  return {
    ...alert,
    body: guidance?.body || alert.body,
    daysRemaining: alert.daysRemaining,
    timingStatus: alert.timingStatus,
    whatYouNeed: alert.whatYouNeed?.length ? alert.whatYouNeed : guidance?.whatYouNeed || fallbackWhatYouNeed(alert),
    steps: alert.steps?.length ? alert.steps : guidance?.steps || fallbackSteps(alert),
  };
}

// The agent owns the canonical estate shape; the ported UI screens read the
// lighter EstateProfile/ExecutorProfile shapes. Map the real, logged-in data
// into those so login reflects who you actually are.
function toExecutorProfile(user: PublicUser): ExecutorProfile {
  return {
    ...EXECUTOR_PROFILE,
    name: user.name,
    email: user.email,
    phone: user.phone ?? "",
    state: user.state ?? "California",
    county: user.county ?? "",
    relationship: user.relationship ?? "",
  };
}

function toEstateProfile(estate: EstateState, user: PublicUser): EstateProfile {
  return {
    id: estate.id,
    deceasedName: estate.deceasedName,
    role: "Executor",
    relationship: user.relationship ?? "",
    state: "California",
    county: user.county ?? "Not set",
    phase: estate.phase,
    // The seeded demo estate drives the rich cosmetic screens; real estates
    // start empty until documents are parsed.
    seeded: estate.id === "demo-milligan",
    // Chat and letters unlock once the estate actually has a document on file
    // (the demo always does).
    hasDocuments: estate.id === "demo-milligan" || estate.documents.length > 0,
  };
}

export function AppShell() {
  const router = useRouter();
  const [route, setRoute] = React.useState<Route>("dashboard");
  const [detailId, setDetailId] = React.useState<string | null>(null);
  const [completedIds, setCompletedIds] = React.useState<string[]>([]);
  const [estates, setEstates] = React.useState<EstateProfile[]>([]);
  const [activeEstateId, setActiveEstateId] = React.useState<string>("");
  const [profile, setProfile] = React.useState<ExecutorProfile>(EXECUTOR_PROFILE);
  const [loading, setLoading] = React.useState(true);
  const [showCreate, setShowCreate] = React.useState(false);
  const [showProfile, setShowProfile] = React.useState(false);
  const [notifPrefs, setNotifPrefs] = React.useState<NotifPrefs>({ all: true, deadlines: true, weekly: true, email: false });
  const [liveAlerts, setLiveAlerts] = React.useState<BackendAlert[] | null>(null);
  const [liveEstate, setLiveEstate] = React.useState<EstateState | null>(null);
  const [liveAlertsFailed, setLiveAlertsFailed] = React.useState(false);
  const [completingId, setCompletingId] = React.useState<string | null>(null);
  const [completionError, setCompletionError] = React.useState<string | null>(null);
  const E = DEMO_ESTATE;
  const I = ExecutorIcons;

  React.useEffect(() => {
    if (!activeEstateId) return;
    let cancelled = false;
    const controller = new AbortController();
    setDetailId(null);
    setLiveAlertsFailed(false);
    setCompletionError(null);
    setLiveEstate(null);
    setLiveAlerts(null);
    getEstate(activeEstateId, controller.signal)
      .then((estate) => {
        if (cancelled) return;
        setLiveEstate(estate);
        setLiveAlerts(estate.alerts);
        setEstates((cur) =>
          cur.map((item) =>
            item.id === activeEstateId
              ? { ...item, phase: estate.phase, hasDocuments: item.id === "demo-milligan" || estate.documents.length > 0 }
              : item,
          ),
        );

        return runDeadlineAgent(activeEstateId, controller.signal)
          .then((alerts) => {
            if (cancelled) return null;
            setLiveAlerts(alerts);
            return getEstate(activeEstateId, controller.signal);
          })
          .then((updatedEstate) => {
            if (cancelled || !updatedEstate) return;
            setLiveEstate(updatedEstate);
            setEstates((cur) =>
              cur.map((item) =>
                item.id === activeEstateId
                  ? { ...item, phase: updatedEstate.phase, hasDocuments: item.id === "demo-milligan" || updatedEstate.documents.length > 0 }
                  : item,
              ),
            );
          })
          .catch((error) => {
            if (error instanceof DOMException && error.name === "AbortError") return;
            if (cancelled) return;
            setLiveAlertsFailed(true);
          });
      })
      .catch((error) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        if (cancelled) return;
        setLiveAlerts([]);
        setLiveAlertsFailed(true);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [activeEstateId]);
  const titles: Record<Route, string> = { dashboard: "Dashboard", documents: "Documents", chat: "Estate chat", letters: "Letters" };

  // Load the logged-in user and their estates. A missing/stale session bounces
  // back to /welcome (the middleware also gates this route).
  React.useEffect(() => {
    let cancelled = false;
    getMe()
      .then((me) => {
        if (cancelled) return;
        if (!me) {
          router.replace("/welcome");
          return;
        }
        setProfile(toExecutorProfile(me.user));
        const mapped = me.estates.map((estate) => toEstateProfile(estate, me.user));
        setEstates(mapped);
        if (mapped.length > 0) setActiveEstateId(mapped[0].id);
        setLoading(false);
      })
      .catch(() => {
        if (!cancelled) router.replace("/welcome");
      });
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleLogout() {
    await apiLogout();
    router.replace("/welcome");
  }

  const active = estates.find((e) => e.id === activeEstateId) || estates[0];

  if (loading || !active) {
    return (
      <div style={{ display: "flex", height: "100vh", alignItems: "center", justifyContent: "center", background: "var(--bg-app)", color: "var(--text-muted)", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)" }}>
        {loading ? "Loading your estate…" : "No estate found for your account."}
      </div>
    );
  }

  function navigate(r: Route) {
    setDetailId(null);
    setCompletionError(null);
    setRoute(r);
  }
  function openStep(id: string) {
    setCompletionError(null);
    setDetailId(id);
  }
  async function completeStep(id: string) {
    setCompletionError(null);
    setCompletingId(id);
    try {
      const estate = await completeAlert(activeEstateId, id);
      setCompletedIds((c) => (c.includes(id) ? c : [...c, id]));
      setLiveEstate(estate);
      setLiveAlerts(estate.alerts);
      setEstates((cur) =>
        cur.map((item) =>
          item.id === activeEstateId
            ? { ...item, phase: estate.phase, hasDocuments: item.id === "demo-milligan" || estate.documents.length > 0 }
            : item,
        ),
      );
      setDetailId(null);
    } catch (error) {
      setCompletionError(error instanceof Error ? error.message : "We couldn't mark that step complete.");
    } finally {
      setCompletingId(null);
    }
  }
  function switchEstate(id: string) {
    setActiveEstateId(id);
    setDetailId(null);
    setCompletionError(null);
    setRoute("dashboard");
  }
  // After a document is parsed, re-fetch the estate so chat/letters unlock
  // (hasDocuments flips once the backend has a document on file).
  async function refreshEstate(id: string) {
    try {
      const estate = await getEstate(id);
      setEstates((cur) =>
        cur.map((e) =>
          e.id === id
            ? { ...e, phase: estate.phase, hasDocuments: e.id === "demo-milligan" || estate.documents.length > 0 }
            : e,
        ),
      );
    } catch {
      /* leave the current profile in place if the refresh fails */
    }
  }
  function createEstate(est: EstateProfile) {
    setEstates((c) => [...c, est]);
    setActiveEstateId(est.id);
    setShowCreate(false);
    setDetailId(null);
    setRoute("dashboard");
  }

  const guidanceAlerts = [...E.alerts, ...(E.alertsNext || [])];
  const allAlerts: DesignAlert[] = liveAlerts === null
    ? []
    : liveAlerts.length > 0
      ? liveAlerts.map((a) => toDisplayAlert(a, guidanceAlerts))
      : active.seeded
        ? []
        : guidanceAlerts;
  const detailItem = detailId ? allAlerts.find((a) => a.id === detailId) || null : null;
  const detailCompleted = detailItem
    ? completedIds.includes(detailItem.id) || Boolean((detailItem as BackendAlert).dismissed)
    : false;

  let body: React.ReactNode;
  let crumb: string;
  if (detailItem) {
    crumb = "What needs your attention";
    body = (
      <StepDetailScreen
        item={detailItem}
        completed={detailCompleted}
        completing={completingId === detailItem.id}
        error={completionError}
        onBack={() => setDetailId(null)}
        onComplete={completeStep}
      />
    );
  } else {
    crumb = titles[route];
    if (route === "dashboard")
      body = <DashboardScreen key={active.id} estate={active} completedIds={completedIds} onOpenStep={openStep} onGoDocuments={() => navigate("documents")} liveAlerts={liveAlerts} liveEstate={liveEstate} liveAlertsFailed={liveAlertsFailed} />;
    else if (route === "documents") body = <UploadScreen key={active.id} estate={active} onDocumentsChanged={() => refreshEstate(active.id)} />;
    else if (route === "chat") body = <ChatScreen key={active.id} estate={active} />;
    else if (route === "letters") body = <LettersScreen key={active.id} estate={active} />;
    else body = <DashboardScreen key={active.id} estate={active} completedIds={completedIds} onOpenStep={openStep} onGoDocuments={() => navigate("documents")} />;
  }

  return (
    <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
      <Sidebar
        active={route}
        onNavigate={(r) => navigate(r as Route)}
        estates={estates}
        activeEstateId={activeEstateId}
        onSwitchEstate={switchEstate}
        onCreateEstate={() => setShowCreate(true)}
        profile={profile}
        onEditProfile={() => setShowProfile(true)}
        onLogout={handleLogout}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        <div style={{ height: 56, flex: "none", borderBottom: "1px solid var(--border-subtle)", background: "var(--paper-50)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "0 28px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "var(--text-sm)", color: "var(--text-muted)" }}>
            <span>Estate of {active.deceasedName}</span>
            <I.ChevronRight size={14} color="var(--text-subtle)" />
            <span style={{ color: "var(--text-strong)", fontWeight: 600 }}>{crumb}</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <NotificationsMenu prefs={notifPrefs} setPrefs={setNotifPrefs} />
          </div>
        </div>
        <main style={{ flex: 1, overflowY: "auto", minHeight: 0 }}>{body}</main>
      </div>

      <CreateEstateModal open={showCreate} onCancel={() => setShowCreate(false)} onCreate={createEstate} />
      <ProfileEditorModal open={showProfile} profile={profile} onCancel={() => setShowProfile(false)} onSave={(p) => { setProfile(p); setShowProfile(false); }} />
    </div>
  );
}
