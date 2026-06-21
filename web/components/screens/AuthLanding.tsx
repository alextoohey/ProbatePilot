"use client";

import React from "react";
import { Button, Input, Select } from "@/components/ds";
import { AuthError, login as apiLogin, register as apiRegister } from "@/lib/agentClient";

// Marketing landing + log in + a 3-step sign-up wizard (executor account, the
// deceased's details, the estate). Ported from the design system's
// templates/auth-landing/AuthLanding.dc.html. Reuses the DS primitives and
// design tokens so it matches the rest of the app verbatim.

type Screen = "landing" | "login" | "signup";

const RELATIONSHIPS = ["Spouse", "Child", "Parent", "Sibling", "Other family", "Friend", "Attorney", "Other"];
const PROBATE_STATES = ["California", "Arizona", "Nevada", "Oregon", "Washington", "Texas", "New York", "Florida", "Illinois", "Other"];
const STEP_LABELS: Record<number, string> = { 1: "Your account", 2: "Who you're helping", 3: "About the estate" };

function Wordmark() {
  return (
    <svg width="142" height="30" viewBox="0 0 300 64" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Executor AI">
      <rect width="64" height="64" rx="14" fill="#245038" />
      <path d="M16 44 L28 32 L37 39 L48 22" stroke="#F1F7F3" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="16" cy="44" r="3.6" fill="#6BA883" />
      <circle cx="48" cy="22" r="4.6" fill="#F1F7F3" />
      <text x="82" y="41" fontFamily="Newsreader, Georgia, serif" fontSize="32" fontWeight="600" fill="#1F2933" letterSpacing="-0.5">Executor</text>
      <text x="232" y="41" fontFamily="'Hanken Grotesk', sans-serif" fontSize="32" fontWeight="700" fill="#245038" letterSpacing="-0.5">AI</text>
    </svg>
  );
}

function LogoButton({ onClick, style }: { onClick: () => void; style?: React.CSSProperties }) {
  return (
    <button onClick={onClick} aria-label="Executor AI home" style={{ background: "none", border: "none", padding: 0, cursor: "pointer", display: "inline-flex", ...style }}>
      <Wordmark />
    </button>
  );
}

const Check = ({ size = 18, stroke = "var(--evergreen-700)", width = 2 }: { size?: number; stroke?: string; width?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={stroke} strokeWidth={width} strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
);

const labelStyle: React.CSSProperties = { display: "block", fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)", marginBottom: "6px" };
const errorBox: React.CSSProperties = { margin: "16px 0 0", color: "var(--critical-text)", fontSize: "var(--text-sm)", background: "var(--critical-bg)", border: "1px solid var(--critical-border)", borderRadius: "var(--radius-md)", padding: "8px 12px" };
const asideStyle: React.CSSProperties = { flex: "1 1 44%", maxWidth: 560, minWidth: 0, background: "var(--surface-tint)", borderRight: "1px solid var(--border-subtle)", padding: 48, display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 40 };
const mainPaneStyle: React.CSSProperties = { flex: "1 1 56%", minWidth: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: "48px 32px" };
const disclaimer = "Information, not legal advice. Executor AI is not a law firm.";
const welcomeHeroPhoto = "/assets/welcome-family-advisor.jpg";

function firstName(full: string) {
  return (full || "").trim().split(/\s+/)[0] || "";
}

export function AuthLanding({
  startScreen = "landing",
  onEnterApp,
}: {
  startScreen?: Screen;
  // Called when the user logs in or finishes sign-up — host decides where to go.
  onEnterApp?: () => void;
}) {
  const [screen, setScreen] = React.useState<Screen>(startScreen);
  const [step, setStep] = React.useState(1);
  const [signupDone, setSignupDone] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const [loginEmail, setLoginEmail] = React.useState("");
  const [loginPassword, setLoginPassword] = React.useState("");
  const [loginError, setLoginError] = React.useState("");

  const [name, setName] = React.useState("");
  const [email, setEmail] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [phone, setPhone] = React.useState("");

  const [decName, setDecName] = React.useState("");
  const [dod, setDod] = React.useState("");
  const [relationship, setRelationship] = React.useState("Spouse");

  const [estState, setEstState] = React.useState("California");
  const [county, setCounty] = React.useState("");
  const [hasWill, setHasWill] = React.useState("yes");
  const [stepError, setStepError] = React.useState("");

  function go(next: Screen) {
    setScreen(next);
    setStep(1);
    setSignupDone(false);
    setStepError("");
    setLoginError("");
  }

  function nextStep() {
    let err = "";
    if (step === 1) {
      if (!name.trim() || !email.trim() || !password) err = "Please fill in your name, email, and a password.";
      else if (!/.+@.+\..+/.test(email)) err = "That email doesn't look right. Please check it.";
      else if (password.length < 8) err = "Choose a password with at least 8 characters.";
    } else if (step === 2) {
      if (!decName.trim()) err = "Please enter the full name of the person who died.";
    }
    if (err) { setStepError(err); return; }
    setStep((s) => Math.min(3, s + 1));
    setStepError("");
  }

  function prevStep() {
    setStep((s) => Math.max(1, s - 1));
    setStepError("");
  }

  async function submitSignup() {
    if (!county.trim()) { setStepError("Please add the county where probate will be filed."); return; }
    setStepError("");
    setBusy(true);
    try {
      await apiRegister({
        name: name.trim(),
        email: email.trim(),
        password,
        phone: phone.trim() || null,
        deceasedName: decName.trim(),
        dateOfDeath: dod || null,
        relationship,
        state: estState,
        county: county.trim(),
        hasWill,
      });
      setSignupDone(true);
    } catch (err) {
      // A taken email comes back at step 1, where the email field lives.
      if (err instanceof AuthError && err.status === 409) {
        setStep(1);
        setStepError(err.message);
      } else {
        setStepError(err instanceof AuthError ? err.message : "Something went wrong creating your account. Please try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function login() {
    if (!loginEmail.trim() || !loginPassword) { setLoginError("Enter your email and password to continue."); return; }
    setLoginError("");
    setBusy(true);
    try {
      await apiLogin({ email: loginEmail.trim(), password: loginPassword });
      onEnterApp?.();
    } catch (err) {
      setLoginError(err instanceof AuthError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  const decFirst = firstName(decName);
  const successHeadline = decFirst ? `${decFirst}'s estate is ready` : "Your estate workspace is ready";

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg-app)", fontFamily: "var(--font-sans)", color: "var(--text-body)" }}>
      {screen === "landing" && (
        <div>
          <header style={{ position: "fixed", top: 0, left: 0, right: 0, zIndex: 10, background: "rgba(227,239,231,0.28)", backdropFilter: "blur(18px) saturate(1.2)", WebkitBackdropFilter: "blur(18px) saturate(1.2)", borderBottom: "1px solid rgba(195,221,205,0.28)" }}>
            <div style={{ maxWidth: "var(--container-lg)", margin: "0 auto", padding: "14px 32px", display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16 }}>
              <LogoButton onClick={() => go("landing")} />
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <Button variant="ghost" onClick={() => go("login")}>Log in</Button>
                <Button variant="primary" onClick={() => go("signup")}>Get started</Button>
              </div>
            </div>
          </header>

          <section
            style={{
              minHeight: "100vh",
              display: "flex",
              alignItems: "center",
              backgroundColor: "var(--ink-950)",
              backgroundImage: `linear-gradient(90deg, rgba(17,24,28,0.82) 0%, rgba(17,24,28,0.62) 42%, rgba(17,24,28,0.22) 72%, rgba(17,24,28,0.08) 100%), url(${welcomeHeroPhoto})`,
              backgroundSize: "cover",
              backgroundPosition: "center center",
              borderBottom: "1px solid rgba(17,24,28,0.12)",
            }}
          >
            <div style={{ width: "100%", maxWidth: "var(--container-lg)", margin: "0 auto", padding: "132px 32px 68px" }}>
              <div style={{ maxWidth: 690 }}>
                <p style={{ margin: "0 0 18px", fontFamily: "var(--font-sans)", fontSize: "var(--text-xs)", fontWeight: 700, letterSpacing: "var(--tracking-caps)", textTransform: "uppercase", color: "rgba(241,247,243,0.84)" }}>The expert in your corner</p>
                <h1 style={{ margin: "0 0 22px", fontFamily: "var(--font-display)", fontSize: "var(--text-5xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--paper-50)", textWrap: "balance", textShadow: "0 2px 24px rgba(0,0,0,0.28)" }}>You shouldn&apos;t have to learn probate law while you&apos;re grieving.</h1>
                <p style={{ margin: "0 0 32px", fontSize: "var(--text-md)", lineHeight: "var(--leading-relaxed)", color: "rgba(241,247,243,0.88)", maxWidth: 610, textShadow: "0 1px 18px rgba(0,0,0,0.22)" }}>Executor AI reads your documents, tracks every deadline, and tells you the one thing to do next, before a missed date can cost you. Plain English, always.</p>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
                <Button variant="primary" size="lg" onClick={() => go("signup")}>Create your account</Button>
                <Button variant="secondary" size="lg" onClick={() => go("login")} style={{ background: "rgba(255,255,255,0.9)", borderColor: "rgba(255,255,255,0.74)" }}>I already have an account</Button>
                </div>
              </div>
            </div>
          </section>

          <section style={{ maxWidth: "var(--container-lg)", margin: "0 auto", padding: "36px 32px 72px" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(260px,1fr))", gap: 20 }}>
              {[
                {
                  title: "Document intelligence",
                  body: "Upload a will, a deed, a bank statement. Executor AI pulls out the assets, debts, beneficiaries, and dates into one living picture of the estate.",
                  icon: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z" /><path d="M14 2v4a2 2 0 0 0 2 2h4" /><path d="M16 13H8" /><path d="M16 17H8" /><path d="M10 9H8" /></svg>),
                },
                {
                  title: "Answers from your estate",
                  body: "Ask anything and get a plain-English answer grounded in your own documents, even hands-free while you're on the phone with the bank.",
                  icon: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>),
                },
                {
                  title: "Deadlines, before they pass",
                  body: "Executor AI reasons over probate rules and surfaces the next action, ranked by urgency and what it costs if missed.",
                  icon: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M10.268 21a2 2 0 0 0 3.464 0" /><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326" /></svg>),
                },
              ].map((f) => (
                <div key={f.title} style={{ background: "var(--surface-card)", border: "1px solid var(--border-subtle)", borderRadius: "var(--radius-lg)", padding: 24, boxShadow: "var(--shadow-sm)" }}>
                  <div style={{ width: 40, height: 40, borderRadius: "var(--radius-md)", background: "var(--evergreen-100)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--evergreen-700)", marginBottom: 16 }}>{f.icon}</div>
                  <h3 style={{ margin: "0 0 8px", fontFamily: "var(--font-display)", fontSize: "var(--text-lg)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", color: "var(--text-strong)" }}>{f.title}</h3>
                  <p style={{ margin: 0, fontSize: "var(--text-base)", lineHeight: "var(--leading-normal)", color: "var(--text-muted)" }}>{f.body}</p>
                </div>
              ))}
            </div>
          </section>

          <section style={{ background: "var(--surface-tint)", borderTop: "1px solid var(--border-subtle)", borderBottom: "1px solid var(--border-subtle)" }}>
            <div style={{ maxWidth: "var(--container-lg)", margin: "0 auto", padding: "56px 32px", display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 24 }}>
              <p style={{ margin: 0, fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-snug)", color: "var(--text-strong)", maxWidth: 620, textWrap: "balance" }}>There is a clear path. We&apos;ll walk it with you.</p>
              <Button variant="primary" size="lg" onClick={() => go("signup")}>Get started</Button>
            </div>
          </section>

          <footer style={{ maxWidth: "var(--container-lg)", margin: "0 auto", padding: 32, display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--text-subtle)" }}>© 2026 Executor AI</span>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--text-subtle)" }}>Executor AI provides information, not legal advice. It is not a law firm.</span>
          </footer>
        </div>
      )}

      {screen === "login" && (
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <aside style={asideStyle}>
            <LogoButton onClick={() => go("landing")} style={{ alignSelf: "flex-start" }} />
            <div>
              <p style={{ margin: "0 0 24px", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-snug)", color: "var(--text-strong)" }}>You shouldn&apos;t have to learn probate law while you grieve. We&apos;ll tell you what&apos;s due, what it means, and the one thing to do next.</p>
              <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
                {["Plain-English answers, every term defined", "Every deadline tracked before it passes", "Honest about its limits, never fake confidence"].map((t) => (
                  <li key={t} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: "var(--text-base)", color: "var(--text-muted)" }}><Check />{t}</li>
                ))}
              </ul>
            </div>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--text-subtle)" }}>{disclaimer}</span>
          </aside>

          <main style={mainPaneStyle}>
            <div style={{ width: "100%", maxWidth: 420 }}>
              <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--text-strong)" }}>Welcome back</h1>
              <p style={{ margin: "0 0 28px", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-normal)" }}>Log in to pick up where you left off.</p>

              <div style={{ display: "grid", gap: 16 }}>
                <Input label="Email" type="email" value={loginEmail} onChange={(e) => { setLoginEmail(e.target.value); setLoginError(""); }} placeholder="you@example.com" />
                <div>
                  <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 6 }}>
                    <label htmlFor="login-pass" style={{ fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-strong)" }}>Password</label>
                    <button type="button" style={{ background: "none", border: "none", color: "var(--text-link)", fontFamily: "var(--font-sans)", fontSize: "var(--text-sm)", fontWeight: 500, cursor: "pointer", padding: 0 }}>Forgot password?</button>
                  </div>
                  <Input id="login-pass" type="password" value={loginPassword} onChange={(e) => { setLoginPassword(e.target.value); setLoginError(""); }} placeholder="Your password" />
                </div>
              </div>

              {loginError && <p style={errorBox}>{loginError}</p>}

              <Button variant="primary" size="lg" fullWidth onClick={login} disabled={busy} style={{ marginTop: 24 }}>{busy ? "Logging in…" : "Log in"}</Button>

              <p style={{ margin: "20px 0 0", textAlign: "center", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
                New to Executor AI? <button type="button" onClick={() => go("signup")} style={{ background: "none", border: "none", color: "var(--text-link)", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", fontWeight: 600, cursor: "pointer", padding: 0, textDecoration: "underline", textUnderlineOffset: "2px" }}>Create an account</button>
              </p>
            </div>
          </main>
        </div>
      )}

      {screen === "signup" && (
        <div style={{ display: "flex", minHeight: "100vh" }}>
          <aside style={asideStyle}>
            <LogoButton onClick={() => go("landing")} style={{ alignSelf: "flex-start" }} />
            <div>
              <p style={{ margin: "0 0 20px", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 500, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-snug)", color: "var(--text-strong)" }}>Let&apos;s set up your estate. It takes about a minute, and you can add documents and the finer details later.</p>
              <p style={{ margin: 0, fontSize: "var(--text-base)", lineHeight: "var(--leading-relaxed)", color: "var(--text-muted)" }}>We only ask for what we need to start tracking the right deadlines for you. Nothing here is shared, and you can change any of it anytime.</p>
            </div>
            <span style={{ fontSize: "var(--text-sm)", color: "var(--text-subtle)" }}>{disclaimer}</span>
          </aside>

          <main style={mainPaneStyle}>
            <div style={{ width: "100%", maxWidth: 460 }}>
              {!signupDone && (
                <div>
                  <div style={{ marginBottom: 28 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
                      <span style={{ fontSize: "var(--text-sm)", fontWeight: 600, color: "var(--text-strong)" }}>{STEP_LABELS[step]}</span>
                      <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--text-muted)", letterSpacing: "0.02em" }}>Step {step} of 3</span>
                    </div>
                    <div style={{ display: "flex", gap: 6 }}>
                      {[1, 2, 3].map((seg) => (
                        <div key={seg} style={{ flex: 1, height: 4, borderRadius: 999, background: step >= seg ? "var(--evergreen-700)" : "var(--surface-sunken)", transition: "background var(--transition-base)" }} />
                      ))}
                    </div>
                  </div>

                  {step === 1 && (
                    <div>
                      <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--text-strong)" }}>Create your account</h1>
                      <p style={{ margin: "0 0 24px", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-normal)" }}>This is your login. We&apos;ll use your email to reach you about deadlines.</p>
                      <div style={{ display: "grid", gap: 16 }}>
                        <Input label="Your full name" value={name} onChange={(e) => { setName(e.target.value); setStepError(""); }} placeholder="e.g. Dana Milligan" />
                        <Input label="Email" type="email" value={email} onChange={(e) => { setEmail(e.target.value); setStepError(""); }} placeholder="you@example.com" />
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                          <Input label="Password" type="password" value={password} onChange={(e) => { setPassword(e.target.value); setStepError(""); }} placeholder="8+ characters" />
                          <div>
                            <label htmlFor="su-phone" style={labelStyle}>Phone <span style={{ color: "var(--text-subtle)", fontWeight: 400 }}>(optional)</span></label>
                            <Input id="su-phone" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="(555) 555-5555" />
                          </div>
                        </div>
                      </div>
                      {stepError && <p style={errorBox}>{stepError}</p>}
                      <Button variant="primary" size="lg" fullWidth onClick={nextStep} style={{ marginTop: 24 }}>Continue</Button>
                      <p style={{ margin: "20px 0 0", textAlign: "center", fontSize: "var(--text-base)", color: "var(--text-muted)" }}>
                        Already have an account? <button type="button" onClick={() => go("login")} style={{ background: "none", border: "none", color: "var(--text-link)", fontFamily: "var(--font-sans)", fontSize: "var(--text-base)", fontWeight: 600, cursor: "pointer", padding: 0, textDecoration: "underline", textUnderlineOffset: "2px" }}>Log in</button>
                      </p>
                    </div>
                  )}

                  {step === 2 && (
                    <div>
                      <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--text-strong)" }}>Who are you helping?</h1>
                      <p style={{ margin: "0 0 24px", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-normal)" }}>Tell us about the person whose estate you&apos;re settling. We&apos;ll address them by name throughout.</p>
                      <div style={{ display: "grid", gap: 16 }}>
                        <Input label="Full name of the person who died" value={decName} onChange={(e) => { setDecName(e.target.value); setStepError(""); }} placeholder="e.g. Robert A. Milligan" />
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                          <Input label="Date of death" type="date" value={dod} onChange={(e) => setDod(e.target.value)} />
                          <Select label="Your relationship to them" value={relationship} onChange={(e) => setRelationship(e.target.value)} options={RELATIONSHIPS} />
                        </div>
                      </div>
                      {stepError && <p style={errorBox}>{stepError}</p>}
                      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
                        <Button variant="secondary" size="lg" onClick={prevStep}>Back</Button>
                        <Button variant="primary" size="lg" onClick={nextStep} style={{ flex: 1 }}>Continue</Button>
                      </div>
                    </div>
                  )}

                  {step === 3 && (
                    <div>
                      <h1 style={{ margin: "0 0 6px", fontFamily: "var(--font-display)", fontSize: "var(--text-2xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--text-strong)" }}>About the estate</h1>
                      <p style={{ margin: "0 0 24px", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-normal)" }}>Probate rules vary by state. This lets Executor AI track the right deadlines for you.</p>
                      <div style={{ display: "grid", gap: 16 }}>
                        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                          <Select label="State of probate" value={estState} onChange={(e) => setEstState(e.target.value)} options={PROBATE_STATES} />
                          <Input label="County" value={county} onChange={(e) => { setCounty(e.target.value); setStepError(""); }} placeholder="e.g. Alameda" />
                        </div>
                        <div>
                          <label style={{ ...labelStyle, marginBottom: 8 }}>Is there a will?</label>
                          <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 8 }}>
                            {[{ v: "yes", l: "Yes" }, { v: "no", l: "No will" }, { v: "unsure", l: "Not sure" }].map((o) => (
                              <label key={o.v} style={{ display: "flex", alignItems: "center", gap: 8, padding: "11px 12px", border: "1px solid var(--border-default)", borderRadius: "var(--radius-md)", cursor: "pointer", fontSize: "var(--text-sm)", color: "var(--text-body)" }}>
                                <input type="radio" name="hasWill" value={o.v} checked={hasWill === o.v} onChange={(e) => setHasWill(e.target.value)} style={{ accentColor: "var(--evergreen-700)", margin: 0 }} />
                                {o.l}
                              </label>
                            ))}
                          </div>
                        </div>
                      </div>
                      {stepError && <p style={errorBox}>{stepError}</p>}
                      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
                        <Button variant="secondary" size="lg" onClick={prevStep} disabled={busy}>Back</Button>
                        <Button variant="primary" size="lg" onClick={submitSignup} disabled={busy} style={{ flex: 1 }}>{busy ? "Creating account…" : "Create account"}</Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {signupDone && (
                <div style={{ textAlign: "center" }}>
                  <div style={{ width: 56, height: 56, borderRadius: "var(--radius-full)", background: "var(--evergreen-100)", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--evergreen-700)", margin: "0 auto 20px" }}>
                    <Check size={28} stroke="currentColor" width={2.25} />
                  </div>
                  <h1 style={{ margin: "0 0 8px", fontFamily: "var(--font-display)", fontSize: "var(--text-3xl)", fontWeight: 600, letterSpacing: "var(--tracking-tight)", lineHeight: "var(--leading-tight)", color: "var(--text-strong)" }}>{successHeadline}</h1>
                  <p style={{ margin: "0 0 28px", fontSize: "var(--text-base)", color: "var(--text-muted)", lineHeight: "var(--leading-relaxed)" }}>Upload a document or two and Executor AI will start building the picture of the estate, and watching the deadlines so you don&apos;t have to.</p>
                  <Button variant="primary" size="lg" onClick={() => onEnterApp?.()}>Go to your dashboard</Button>
                </div>
              )}
            </div>
          </main>
        </div>
      )}
    </div>
  );
}
