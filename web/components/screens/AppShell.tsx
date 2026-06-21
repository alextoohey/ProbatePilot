"use client";

import React from "react";
import { ExecutorIcons } from "@/lib/design/icons";
import {
  DEMO_ESTATE,
  ESTATE_PROFILES,
  EXECUTOR_PROFILE,
  type EstateProfile,
  type ExecutorProfile,
  type Alert as DesignAlert,
} from "@/lib/design/data";
import { runDeadlineAgent, getEstate } from "@/lib/agentClient";
import type { Alert as BackendAlert, EstateState } from "@/types";
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

export function AppShell() {
  const [route, setRoute] = React.useState<Route>("dashboard");
  const [detailId, setDetailId] = React.useState<string | null>(null);
  const [completedIds, setCompletedIds] = React.useState<string[]>([]);
  const [estates, setEstates] = React.useState<EstateProfile[]>(ESTATE_PROFILES);
  const [activeEstateId, setActiveEstateId] = React.useState<string>(ESTATE_PROFILES[0].id);
  const [profile, setProfile] = React.useState<ExecutorProfile>(EXECUTOR_PROFILE);
  const [showCreate, setShowCreate] = React.useState(false);
  const [showProfile, setShowProfile] = React.useState(false);
  const [notifPrefs, setNotifPrefs] = React.useState<NotifPrefs>({ all: true, deadlines: true, weekly: true, email: false });
  const [liveAlerts, setLiveAlerts] = React.useState<BackendAlert[] | null>(null);
  const [liveEstate, setLiveEstate] = React.useState<EstateState | null>(null);
  const [liveAlertsFailed, setLiveAlertsFailed] = React.useState(false);
  const E = DEMO_ESTATE;
  const I = ExecutorIcons;

  React.useEffect(() => {
    const est = estates.find((e) => e.id === activeEstateId);
    let cancelled = false;
    setDetailId(null);
    setLiveAlertsFailed(false);
    setLiveEstate(null);
    if (!est?.seeded) {
      setLiveAlerts([]);
      return () => {
        cancelled = true;
      };
    }
    const controller = new AbortController();
    setLiveAlerts(null);
    Promise.all([runDeadlineAgent(activeEstateId, controller.signal), getEstate(activeEstateId, controller.signal)])
      .then(([alerts, estate]) => {
        if (cancelled) return;
        setLiveAlerts(alerts);
        setLiveEstate(estate);
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
  }, [activeEstateId, estates]);
  const titles: Record<Route, string> = { dashboard: "Dashboard", documents: "Documents", chat: "Estate chat", letters: "Letters" };

  const active = estates.find((e) => e.id === activeEstateId) || estates[0];

  function navigate(r: Route) {
    setDetailId(null);
    setRoute(r);
  }
  function openStep(id: string) {
    setDetailId(id);
  }
  function completeStep(id: string) {
    setCompletedIds((c) => (c.includes(id) ? c : [...c, id]));
    setDetailId(null);
  }
  function switchEstate(id: string) {
    setActiveEstateId(id);
    setDetailId(null);
    setRoute("dashboard");
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
      ? liveAlerts.map((a) => {
        const guidance = guidanceAlerts.find((g) => g.id === a.id);
        return {
          ...a,
          steps: guidance?.steps || [],
          whatYouNeed: guidance?.whatYouNeed || [],
          daysRemaining: a.daysRemaining,
        };
      })
      : active.seeded
        ? []
        : guidanceAlerts;
  const detailItem = active.seeded && detailId ? allAlerts.find((a) => a.id === detailId) || null : null;

  let body: React.ReactNode;
  let crumb: string;
  if (detailItem) {
    crumb = "What needs your attention";
    body = (
      <StepDetailScreen
        item={detailItem}
        completed={completedIds.includes(detailItem.id)}
        onBack={() => setDetailId(null)}
        onComplete={completeStep}
      />
    );
  } else {
    crumb = titles[route];
    if (route === "dashboard")
      body = <DashboardScreen key={active.id} estate={active} completedIds={completedIds} onOpenStep={openStep} onGoDocuments={() => navigate("documents")} liveAlerts={liveAlerts} liveEstate={liveEstate} liveAlertsFailed={liveAlertsFailed} />;
    else if (route === "documents") body = <UploadScreen key={active.id} estate={active} />;
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
