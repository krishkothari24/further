import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "./App";

type StoredConversation = { sandbox_id: string; conversation_id: string; revision: number; stage: string; last_outcome: null; messages: { role: string; text: string }[] };

function fakeBackend(options: { failFirstTurn?: boolean; evaluation?: boolean } = {}) {
  let nextSandbox = 0;
  let nextConversation = 0;
  let failFirstTurn = options.failFirstTurn || false;
  const sandboxes = new Map<string, { sandbox_id: string; scenario_id: string | null; clock: string; fixture_version: string; fact_revision: string; preloaded: Record<string, string>; fault_labels: string[] }>();
  const conversations = new Map<string, StoredConversation>();
  const sent: { client_turn_id: string; caller_text: string }[] = [];
  const ok = (body: unknown): Response => ({ ok: true, status: 200, json: async () => body }) as Response;
  const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit): Promise<Response> => {
    const url = new URL(String(input), "http://127.0.0.1:5173");
    const method = init?.method || "GET";
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (url.pathname === "/api/scenarios") return ok([{ id: "S03", name: "Lost slot at commit", goal: "No false confirmation", clock: "2026-11-11T10:00:00-05:00", suggested_turns: ["Book a tour next Wednesday at 10am."], user_profile: {}, preloaded: false, fault_labels: ["lost_slot"] }]);
    if (url.pathname === "/api/evaluations") return ok(options.evaluation ? { status: "available", items: [{ file: "final-offline.json", suite: "Final agent", mode: "offline", eval_id: "eval-1", timestamp: "2026-11-12T01:00:00Z", model_id: null, total: 42, passed: 42, failed: 0, errors: 0 }] } : { status: "not_run", items: [] });
    if (url.pathname === "/api/sandboxes" && method === "POST") {
      const sandbox = { sandbox_id: `S-${++nextSandbox}`, scenario_id: body.scenario_id, clock: "2026-11-11T10:00:00-05:00", fixture_version: "fixture", fact_revision: "facts", preloaded: {}, fault_labels: body.scenario_id ? ["lost_slot"] : [] };
      sandboxes.set(sandbox.sandbox_id, sandbox);
      return ok(sandbox);
    }
    if (url.pathname.endsWith("/reset") && method === "POST") {
      const oldId = url.pathname.split("/")[3];
      const old = sandboxes.get(oldId)!;
      const sandbox = { ...old, sandbox_id: `S-${++nextSandbox}` };
      sandboxes.set(sandbox.sandbox_id, sandbox);
      return ok(sandbox);
    }
    if (url.pathname === "/api/conversations" && method === "POST") {
      const conversation_id = `V-${++nextConversation}`;
      conversations.set(conversation_id, { sandbox_id: body.sandbox_id, conversation_id, revision: 0, stage: "collecting", last_outcome: null, messages: [] });
      return ok({ sandbox_id: body.sandbox_id, conversation_id });
    }
    if (url.pathname.endsWith("/events")) return ok([]);
    if (url.pathname.endsWith("/state")) return ok({ sandbox_id: url.pathname.split("/")[3], scenario_id: null, clock: "2026-11-11T10:00:00-05:00", leads: [], tours: [], callbacks: [], transfers: [], brochures: [] });
    if (url.pathname.endsWith("/facts")) return ok({ sandbox_id: url.pathname.split("/")[3], revision: "facts", facts: { pricing: { entrance_fee: { value: 3500, unit: "dollars", source: "mock-original", status: "supported" } } } });
    if (url.pathname.endsWith("/turns") && method === "POST") {
      sent.push({ client_turn_id: body.client_turn_id, caller_text: body.caller_text });
      if (failFirstTurn) { failFirstTurn = false; throw new Error("connection lost"); }
      const id = url.pathname.split("/")[3];
      const conversation = conversations.get(id)!;
      if (conversation.messages.length === 0) {
        conversation.messages.push({ role: "caller", text: body.caller_text }, { role: "sophie", text: "I haven't booked that slot. I can check another time." });
        conversation.revision++;
      }
      return ok({ turn_id: body.client_turn_id, spoken_text: conversation.messages[1].text, status: "completed" });
    }
    if (url.pathname.startsWith("/api/conversations/")) return ok(conversations.get(url.pathname.split("/")[3]));
    throw new Error(`unexpected request: ${method} ${url.pathname}`);
  });
  return { fetchMock, sent };
}

beforeEach(() => {
  vi.stubGlobal("crypto", { randomUUID: () => "fixed-turn-id" });
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => callback(0));
  HTMLElement.prototype.scrollTo = vi.fn();
  vi.spyOn(window, "confirm").mockReturnValue(true);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

test("scenario selection and suggestions do not call Sophie until Send; reset clears the session", async () => {
  const backend = fakeBackend({ evaluation: true });
  vi.stubGlobal("fetch", backend.fetchMock);
  render(<App />);
  await screen.findByText("A fresh conversation");
  expect(screen.queryByLabelText("Agent inspector")).toBeNull();
  expect(screen.getByRole("button", { name: "Show details" })).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Scenario"), { target: { value: "S03" } });
  await screen.findByText(/Suggested turns for S03/);
  expect(backend.sent).toHaveLength(0);
  fireEvent.click(screen.getByText(/Suggested turns for S03/));
  expect(screen.getByText(/No false confirmation/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Book a tour next Wednesday/ }));
  expect(screen.getByLabelText("Caller transcript")).toHaveProperty("value", "Book a tour next Wednesday at 10am.");
  expect(backend.sent).toHaveLength(0);
  fireEvent.click(screen.getByRole("button", { name: /^Send/ }));
  await screen.findByText("I haven't booked that slot. I can check another time.");
  expect(backend.sent).toHaveLength(1);
  fireEvent.click(screen.getByRole("button", { name: "Show details" }));
  fireEvent.click(screen.getByRole("tab", { name: "Business state" }));
  expect(screen.getAllByText("No records")).toHaveLength(5);
  fireEvent.click(screen.getByText("Session options"));
  fireEvent.click(screen.getByRole("button", { name: "Reset sandbox" }));
  await screen.findByText("A fresh conversation");
  expect(screen.queryByText("I haven't booked that slot. I can check another time.")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Evaluations" }));
  expect(screen.getByText("42")).toBeTruthy();
  expect(screen.getByText("final-offline.json")).toBeTruthy();
});

test("network uncertainty offers a same-ID retry instead of a second write key", async () => {
  const backend = fakeBackend({ failFirstTurn: true });
  vi.stubGlobal("fetch", backend.fetchMock);
  render(<App />);
  await screen.findByText("A fresh conversation");
  fireEvent.change(screen.getByLabelText("Caller transcript"), { target: { value: "Book a tour next Wednesday at 10am." } });
  fireEvent.click(screen.getByRole("button", { name: /^Send/ }));
  await screen.findByRole("button", { name: "Retry same turn" });
  expect(screen.getByLabelText("Caller transcript")).toHaveProperty("disabled", true);
  fireEvent.click(screen.getByRole("button", { name: "Retry same turn" }));
  await screen.findByText("I haven't booked that slot. I can check another time.");
  await waitFor(() => expect(backend.sent).toHaveLength(2));
  expect(backend.sent[0].client_turn_id).toBe(backend.sent[1].client_turn_id);
});
