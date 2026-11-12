import type { BusinessState, Conversation, Evaluations, Event, Facts, Sandbox, Scenario, TurnResult } from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError("Cannot reach the local Sophie API. Start the backend, then retry this turn.", 0);
  }
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body && typeof body === "object" && "detail" in body ? String(body.detail) : response.statusText;
    throw new ApiError(`API ${response.status}: ${detail}`, response.status);
  }
  return body as T;
}

const json = (value: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(value) });
const scope = (id: string) => encodeURIComponent(id);

export const api = {
  scenarios: () => request<Scenario[]>("/api/scenarios"),
  createSandbox: (scenarioId: string | null) => request<Sandbox>("/api/sandboxes", json({ scenario_id: scenarioId })),
  resetSandbox: (sandboxId: string) => request<Sandbox>(`/api/sandboxes/${scope(sandboxId)}/reset`, json({})),
  createConversation: (sandboxId: string) => request<{ conversation_id: string }>("/api/conversations", json({ sandbox_id: sandboxId })),
  conversation: (sandboxId: string, conversationId: string) => request<Conversation>(`/api/conversations/${scope(conversationId)}?sandbox_id=${scope(sandboxId)}`),
  events: (sandboxId: string, conversationId: string) => request<Event[]>(`/api/conversations/${scope(conversationId)}/events?sandbox_id=${scope(sandboxId)}`),
  state: (sandboxId: string) => request<BusinessState>(`/api/sandboxes/${scope(sandboxId)}/state`),
  facts: (sandboxId: string) => request<Facts>(`/api/sandboxes/${scope(sandboxId)}/facts`),
  evaluations: () => request<Evaluations>("/api/evaluations"),
  send: (sandboxId: string, conversationId: string, turnId: string, callerText: string) =>
    request<TurnResult>(`/api/conversations/${scope(conversationId)}/turns`,
      json({ sandbox_id: sandboxId, client_turn_id: turnId, caller_text: callerText })),
};
