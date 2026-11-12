import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { BusinessState, Conversation, Evaluations, Event, Facts, Sandbox, Scenario } from "./types";

type Session = { sandbox: Sandbox; conversationId: string };
type Busy = "starting" | "sending" | "resetting" | null;
type InspectorTab = "events" | "state" | "facts";

function localClock(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York", weekday: "short", month: "short", day: "numeric",
    year: "numeric", hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(new Date(value));
}

function displayValue(value: unknown, unit?: string): string {
  if (value === null || value === undefined || value === "") return "Not established";
  const rendered = typeof value === "object" ? JSON.stringify(value) : String(value);
  return unit && unit !== "none" ? `${rendered} ${unit}` : rendered;
}

function Section({ title, count, children }: { title: string; count: number; children: React.ReactNode }) {
  return <section className="record-section">
    <h3>{title} <span className="count">{count}</span></h3>
    {count ? <div className="record-list">{children}</div> : <p className="muted empty-record">No records</p>}
  </section>;
}

function BusinessInspector({ state }: { state: BusinessState | null }) {
  if (!state) return <p className="muted">Loading persisted state…</p>;
  return <div className="inspector-scroll">
    <p className="inspector-note">Read-only SQLite state. Seeded records are marked as fixture setup.</p>
    <Section title="Tours" count={state.tours.length}>
      {state.tours.map(tour => <article className="record" key={tour.id}>
        <div className="record-top"><strong>{tour.id}</strong><span className={`status-tag ${tour.status}`}>{tour.status}</span></div>
        <p>{tour.local_date} at {tour.local_time} · Eastern time</p>
        <small>Lead {tour.lead_id}{tour.seeded ? " · Seeded fixture" : " · Verified sandbox record"}</small>
      </article>)}
    </Section>
    <Section title="Leads" count={state.leads.length}>
      {state.leads.map(lead => <article className="record" key={lead.id}>
        <div className="record-top"><strong>{lead.name_masked}</strong><span className="record-id">{lead.id}</span></div>
        <small>{lead.email_masked || lead.phone_masked || "No contact shown"}{lead.seeded ? " · Seeded" : ""}</small>
      </article>)}
    </Section>
    <Section title="Callback requests" count={state.callbacks.length}>
      {state.callbacks.map(item => <article className="record" key={item.id}><div className="record-top"><strong>{item.id}</strong><span className="status-tag simulated">{item.status} · simulated</span></div><small>Lead {item.lead_id}</small></article>)}
    </Section>
    <Section title="Human requests" count={state.transfers.length}>
      {state.transfers.map(item => <article className="record" key={item.id}><div className="record-top"><strong>{item.id}</strong><span className="status-tag simulated">{item.status} · simulated</span></div><small>No live connection is made</small></article>)}
    </Section>
    <Section title="Brochure requests" count={state.brochures.length}>
      {state.brochures.map(item => <article className="record" key={item.id}><div className="record-top"><strong>{item.id}</strong><span className="status-tag simulated">{item.status} · simulated</span></div><small>No physical mailing is sent</small></article>)}
    </Section>
  </div>;
}

function EventsInspector({ events }: { events: Event[] }) {
  if (!events.length) return <div className="empty-inspector"><span className="empty-icon">⌁</span><h3>No events yet</h3><p>Tool requests and validation will appear after a caller turn.</p></div>;
  return <ol className="event-list inspector-scroll">
    {events.map(event => <li className="event" key={event.event_id}>
      <div className="event-rail"><span className="event-dot" /></div>
      <div className="event-body">
        <div className="event-meta"><span>Turn {event.turn_id}</span><span>{event.stage.replaceAll("_", " ")}</span></div>
        <strong>{event.tool_name || event.outcome || "Runtime event"}</strong>
        {event.outcome && event.tool_name && <p className="event-outcome">{event.outcome.replaceAll("_", " ")}</p>}
        {event.entity_id && <p className="event-outcome">Record {event.entity_id}</p>}
        {event.error_class && <p className="event-error">{event.error_class}</p>}
        {event.redacted_params && Object.keys(event.redacted_params).length > 0 &&
          <details className="event-details"><summary>Safe request details</summary><pre>{JSON.stringify(event.redacted_params, null, 2)}</pre></details>}
      </div>
    </li>)}
  </ol>;
}

function FactsInspector({ facts }: { facts: Facts | null }) {
  if (!facts) return <p className="muted">Loading canonical facts…</p>;
  return <div className="inspector-scroll facts-list">
    <p className="inspector-note">Canonical registry · {facts.revision}. Unknown fields remain unconfirmed.</p>
    {Object.entries(facts.facts).map(([topic, fields]) => <details key={topic} className="fact-topic">
      <summary>{topic.replaceAll("_", " ")} <span>{Object.keys(fields).length}</span></summary>
      <div>{Object.entries(fields).map(([name, fact]) => <div className="fact-row" key={name}>
        <div><strong>{name.replaceAll("_", " ")}</strong><span className={`fact-status ${fact.status}`}>{fact.status}</span></div>
        <p>{displayValue(fact.value, fact.unit)}</p>
        <small>Source: {fact.source}</small>
      </div>)}</div>
    </details>)}
  </div>;
}

function EvaluationView({ report, onRefresh, busy }: { report: Evaluations | null; onRefresh: () => void; busy: boolean }) {
  return <main className="evaluation-page">
    <div className="page-heading"><div><p className="eyebrow">Evidence / Promptfoo</p><h1>Evaluation results</h1><p>Read-only summaries from saved local run files. The playground never runs a grader.</p></div><button className="secondary-button" onClick={onRefresh} disabled={busy}>Refresh results</button></div>
    {!report || report.status === "not_run" || report.items.length === 0 ? <div className="empty-evals"><span className="empty-icon">◇</span><h2>No evaluation run found</h2><p>Run the documented Promptfoo command, then refresh this page. No score is shown until a saved result file exists.</p><code>npx promptfoo eval</code></div> :
      <div className="eval-grid">{report.items.map(item => <article className="eval-card" key={item.file}>
        <div className="eval-card-head"><span className="eyebrow">{item.mode === "offline" ? "Offline runtime" : "Live model"}</span><span className="status-tag">Saved run</span></div>
        <h2>{item.suite}</h2>
        {item.suite === "Reconstructed baseline" && <p className="muted">Inherited prompt, tools, mock, and seed assertions. Not comparable to the corrected final suite by score alone.</p>}
        {item.mode === "offline" && <p className="muted">No model calls; verifies runtime, scenarios, state, and assertions.</p>}
        <div className="eval-numbers"><div><strong>{item.passed}</strong><span>Passed</span></div><div><strong>{item.failed}</strong><span>Failed</span></div><div><strong>{item.errors}</strong><span>Errors</span></div></div>
        <div className="eval-details"><span>{item.total} cases</span><span>{item.timestamp ? new Date(item.timestamp).toLocaleString() : "Time unavailable"}</span><span>{item.model_id || "No model ID"}</span><code>{item.file}</code></div>
      </article>)}</div>}
    <p className="eval-footnote">Raw artifacts stay local in <code>evals/artifacts/</code> and may contain caller text. Summary counts come from the files above.</p>
  </main>;
}

export default function App() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [business, setBusiness] = useState<BusinessState | null>(null);
  const [facts, setFacts] = useState<Facts | null>(null);
  const [evaluations, setEvaluations] = useState<Evaluations | null>(null);
  const [draft, setDraft] = useState("");
  const [retry, setRetry] = useState<{ id: string; text: string } | null>(null);
  const [busy, setBusy] = useState<Busy>("starting");
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState<"playground" | "evaluations">("playground");
  const [mode, setMode] = useState<"caller" | "debug">("debug");
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("events");
  const busyRef = useRef(true);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const transcriptRef = useRef<HTMLDivElement>(null);
  const selectedScenario = scenarios.find(item => item.id === session?.sandbox.scenario_id);

  async function loadSession(next: Session) {
    const [newConversation, newEvents, newState, newFacts] = await Promise.all([
      api.conversation(next.sandbox.sandbox_id, next.conversationId),
      api.events(next.sandbox.sandbox_id, next.conversationId),
      api.state(next.sandbox.sandbox_id), api.facts(next.sandbox.sandbox_id),
    ]);
    setConversation(newConversation);
    setEvents(newEvents);
    setBusiness(newState);
    setFacts(newFacts);
    setSession(next);
  }

  useEffect(() => {
    let canceled = false;
    async function initialize() {
      try {
        const [list, report] = await Promise.all([api.scenarios(), api.evaluations()]);
        if (canceled) return;
        setScenarios(list);
        setEvaluations(report);
        const sandbox = await api.createSandbox(null);
        const created = await api.createConversation(sandbox.sandbox_id);
        if (!canceled) await loadSession({ sandbox, conversationId: created.conversation_id });
      } catch (cause) {
        if (!canceled) setError(cause instanceof Error ? cause.message : "The playground could not start.");
      } finally {
        if (!canceled) { busyRef.current = false; setBusy(null); }
      }
    }
    void initialize();
    return () => { canceled = true; };
  }, []);

  useEffect(() => {
    if (conversation?.messages.length) transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [conversation?.messages.length]);

  async function run(kind: Exclude<Busy, null>, operation: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(kind);
    setError(null);
    try { await operation(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Request failed."); }
    finally { busyRef.current = false; setBusy(null); }
  }

  async function startScenario(scenarioId: string) {
    if (retry) return;
    if (conversation?.messages.length && !window.confirm("Start a fresh sandbox and clear this transcript?")) return;
    await run("starting", async () => {
      const sandbox = await api.createSandbox(scenarioId || null);
      const created = await api.createConversation(sandbox.sandbox_id);
      await loadSession({ sandbox, conversationId: created.conversation_id });
      setDraft("");
      setRetry(null);
    });
  }

  async function newSession() {
    if (!session || retry) return;
    if (conversation?.messages.length && !window.confirm("Start a new conversation in this sandbox? Existing business records will remain.")) return;
    await run("starting", async () => {
      const created = await api.createConversation(session.sandbox.sandbox_id);
      await loadSession({ ...session, conversationId: created.conversation_id });
      setDraft("");
    });
  }

  async function resetSandbox() {
    if (!session || retry) return;
    if (conversation?.messages.length && !window.confirm("Reset this sandbox? The conversation and its business records will be cleared.")) return;
    await run("resetting", async () => {
      const sandbox = await api.resetSandbox(session.sandbox.sandbox_id);
      const created = await api.createConversation(sandbox.sandbox_id);
      await loadSession({ sandbox, conversationId: created.conversation_id });
      setDraft("");
    });
  }

  async function sendTurn(pending?: { id: string; text: string }) {
    if (!session) return;
    const text = pending?.text || draft.trim();
    if (!text || (retry && !pending)) return;
    const turn = pending || { id: crypto.randomUUID(), text };
    await run("sending", async () => {
      try {
        await api.send(session.sandbox.sandbox_id, session.conversationId, turn.id, turn.text);
        await loadSession(session);
        setRetry(null);
        setDraft("");
        requestAnimationFrame(() => composerRef.current?.focus());
      } catch (cause) {
        setRetry(turn); // Same ID is reused if a write completed but the response was lost.
        throw cause;
      }
    });
  }

  async function refreshEvaluations() {
    await run("starting", async () => setEvaluations(await api.evaluations()));
  }

  const messageCount = conversation?.messages.length || 0;
  return <div className="app-shell">
    <header className="site-header">
      <div className="brand"><div className="brand-mark" aria-hidden="true">S</div><div><strong>Sophie</strong><span>ACME Senior Living</span></div></div>
      <nav aria-label="Main navigation" className="main-nav">
        <button className={page === "playground" ? "active" : ""} onClick={() => setPage("playground")}>Playground</button>
        <button className={page === "evaluations" ? "active" : ""} onClick={() => setPage("evaluations")}>Evaluations</button>
      </nav>
      <span className="sandbox-pill"><span className="pill-dot" /> Sandbox · simulated actions</span>
    </header>

    {page === "evaluations" ? <EvaluationView report={evaluations} onRefresh={() => void refreshEvaluations()} busy={busy !== null} /> : <main className="playground-page">
      <div className="workspace-top">
        <div className="workspace-title"><p className="eyebrow">Text conversation / Local sandbox</p><h1>Talk with Sophie<span className="title-period">.</span></h1><p>Type what a caller would say. Sophie replies through the real agent runtime.</p></div>
        <div className="workspace-controls"><label htmlFor="scenario-select">Scenario</label><select id="scenario-select" value={session?.sandbox.scenario_id || ""} onChange={event => void startScenario(event.target.value)} disabled={busy !== null || !!retry}>
          <option value="">Freeform conversation</option>{scenarios.map(item => <option value={item.id} key={item.id}>{item.id} · {item.name}</option>)}
        </select><div className="session-buttons"><button className="secondary-button" onClick={() => void newSession()} disabled={!session || busy !== null || !!retry}>New session</button><button className="secondary-button" onClick={() => void resetSandbox()} disabled={!session || busy !== null || !!retry}>Reset sandbox</button></div></div>
      </div>

      <div className="workspace-meta"><span><span className="meta-dot" />{selectedScenario ? `${selectedScenario.id} · ${selectedScenario.name}` : "Freeform conversation"}</span><span>{session ? `Sandbox clock · ${localClock(session.sandbox.clock)}` : "Connecting to sandbox…"}</span><span>{session?.sandbox.fault_labels.length ? `Test fault · ${session.sandbox.fault_labels.join(", ")}` : "Canonical facts"}</span></div>

      <div className="mode-row"><div className="segmented" role="group" aria-label="View mode"><button aria-pressed={mode === "caller"} className={mode === "caller" ? "selected" : ""} onClick={() => setMode("caller")}>Caller preview</button><button aria-pressed={mode === "debug"} className={mode === "debug" ? "selected" : ""} onClick={() => setMode("debug")}>Debug view</button></div><span className="mode-help">{mode === "debug" ? "Live events and persisted state" : "Spoken text only"}</span></div>

      <div className={`workspace-grid ${mode === "caller" ? "preview" : ""}`}>
        <section className="conversation-panel" aria-label="Conversation">
          <div className="panel-header"><div><p className="eyebrow">Conversation</p><h2>Call transcript</h2></div><span className="turn-count">{Math.floor(messageCount / 2)} turns</span></div>
          <div className="transcript" ref={transcriptRef} aria-live="polite">
            {!messageCount ? <div className="empty-conversation"><div className="empty-orbit" aria-hidden="true"><span>S</span></div><h3>A fresh conversation</h3><p>Ask about pricing, care options, or a tour. Sophie will answer only from the sandbox's verified facts and actions.</p></div> : conversation?.messages.map((message, index) => <article className={`message ${message.role}`} key={`${index}-${message.role}`}>
              <div className="speaker"><span className="speaker-symbol" aria-hidden="true">{message.role === "caller" ? "C" : "S"}</span><span>{message.role === "caller" ? "Caller · transcribed" : "Sophie · spoken"}</span><small>Turn {Math.floor(index / 2) + 1}</small></div><p>{message.text}</p>
            </article>)}
            {busy === "sending" && <p className="sending-status" role="status"><span className="loading-dot" /> Sending turn to Sophie…</p>}
          </div>
          <div className="composer"><label htmlFor="caller-text">Caller transcript</label><textarea id="caller-text" ref={composerRef} value={draft} onChange={event => setDraft(event.target.value)} onKeyDown={event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void sendTurn(); } }} placeholder="Type the caller's next turn…" rows={3} maxLength={4000} disabled={!session || busy !== null || !!retry} /><div className="composer-bottom"><span>Enter to send · Shift+Enter for a new line</span><button className="primary-button" onClick={() => void sendTurn()} disabled={!session || busy !== null || !!retry || !draft.trim()}>{busy === "sending" ? "Sending…" : "Send turn"}<span aria-hidden="true">↗</span></button></div>
            {retry && <div className="retry-box" role="alert"><p>The response was interrupted. Retry the same turn ID to check its saved result safely.</p><button onClick={() => void sendTurn(retry)} disabled={busy !== null}>Retry same turn</button></div>}
          </div>
        </section>

        {mode === "debug" && <aside className="inspector-panel" aria-label="Agent inspector"><div className="panel-header"><div><p className="eyebrow">Agent inspector</p><h2>What actually happened</h2></div><span className="read-only">Read only</span></div><div className="inspector-tabs" role="tablist" aria-label="Inspector sections">{(["events", "state", "facts"] as InspectorTab[]).map(tab => <button role="tab" aria-selected={inspectorTab === tab} className={inspectorTab === tab ? "active" : ""} key={tab} onClick={() => setInspectorTab(tab)}>{tab === "state" ? "Business state" : tab === "facts" ? "Facts" : "Events"}</button>)}</div><div className="inspector-content">{inspectorTab === "events" ? <EventsInspector events={events} /> : inspectorTab === "state" ? <BusinessInspector state={business} /> : <FactsInspector facts={facts} />}</div></aside>}
      </div>

      {selectedScenario && <section className="scenario-guide"><div><p className="eyebrow">Scenario guide · {selectedScenario.id}</p><h2>{selectedScenario.goal}</h2><p>{selectedScenario.preloaded ? "This fixture begins with seeded, verified state." : "This fixture begins without a tour booking."} Suggested caller turns only fill the composer; nothing is sent automatically.</p></div><div className="suggestion-list">{selectedScenario.suggested_turns.map((text, index) => <button key={`${selectedScenario.id}-${index}`} onClick={() => { setDraft(text); composerRef.current?.focus(); }} disabled={busy !== null || !!retry}><span>{String(index + 1).padStart(2, "0")}</span>{text}</button>)}</div></section>}
      {error && <div className="error-banner" role="alert"><strong>Request issue</strong><span>{error}</span></div>}
    </main>}
    <footer className="site-footer"><span>ACME Senior Living · fictional sandbox</span><span>Callback, transfer, and brochure actions are recorded requests only.</span></footer>
  </div>;
}
