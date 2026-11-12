export type Scenario = {
  id: string;
  name: string;
  goal: string;
  clock: string;
  suggested_turns: string[];
  user_profile: Record<string, string>;
  preloaded: boolean;
  fault_labels: string[];
};

export type Sandbox = {
  sandbox_id: string;
  fixture_version: string;
  fact_revision: string;
  scenario_id: string | null;
  clock: string;
  preloaded: Record<string, string>;
  fault_labels: string[];
};

export type Conversation = {
  sandbox_id: string;
  conversation_id: string;
  revision: number;
  stage: string;
  last_outcome: string | null;
  messages: { role: "caller" | "sophie"; text: string }[];
};

export type Event = {
  event_id: string;
  turn_id: string;
  timestamp: string;
  stage: string;
  tool_name: string | null;
  outcome: string | null;
  error_class: string | null;
  entity_id: string | null;
  redacted_params: Record<string, unknown> | null;
};

export type BusinessState = {
  sandbox_id: string;
  scenario_id: string | null;
  clock: string;
  leads: { id: string; name_masked: string; email_masked: string | null; phone_masked: string | null; seeded: boolean }[];
  tours: { id: string; lead_id: string; local_date: string; local_time: string; timezone: string; starts_at_utc: string; status: string; seeded: boolean }[];
  callbacks: { id: string; lead_id: string | null; status: string; best_time: string | null }[];
  transfers: { id: string; status: string; reason: string | null }[];
  brochures: { id: string; lead_id: string | null; status: string; address_masked: string | null }[];
};

export type Fact = { value: unknown; unit: string; source: string; status: string };
export type Facts = { sandbox_id: string; revision: string; facts: Record<string, Record<string, Fact>> };

export type Evaluation = {
  file: string;
  suite: string;
  mode: "offline" | "live";
  eval_id: string | null;
  timestamp: string | null;
  model_id: string | null;
  total: number;
  passed: number;
  failed: number;
  errors: number;
};
export type Evaluations = { status: "not_run" | "available"; items: Evaluation[] };

export type TurnResult = { spoken_text: string; turn_id: string; status: string };
