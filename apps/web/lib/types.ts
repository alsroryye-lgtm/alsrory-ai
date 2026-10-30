export type AspectRatio = "16:9" | "9:16" | "1:1" | "4:3" | "3:4";

export type Project = {
  id: string;
  name: string;
  description: string;
  aspect_ratio: AspectRatio;
  style_preset: string;
  created_at: string;
  updated_at: string;
  generation_count?: number;
  asset_count?: number;
  cover_asset_id?: string | null;
};

export type Asset = {
  id: string;
  project_id: string;
  generation_id: string | null;
  kind: "video" | "image" | "audio" | "subtitle" | "thumbnail" | "export";
  mime: string;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  size_bytes: number;
  meta: Record<string, unknown>;
  created_at: string;
  url: string;
  download_url: string;
};

export type GenerationStatus =
  | "queued"
  | "running"
  | "postprocessing"
  | "completed"
  | "failed"
  | "canceled";

export type Generation = {
  id: string;
  project_id: string;
  type: string;
  status: GenerationStatus;
  progress: number;
  prompt: string;
  negative_prompt: string;
  params: Record<string, unknown>;
  engine_id: string;
  seed: number | null;
  error_stage: string | null;
  error_detail: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  assets?: Asset[];
};

export type EngineInfo = {
  id: string;
  label: string;
  capabilities: string[];
  is_default: boolean;
  configured: boolean;
};

export type EngineStatus = {
  id: string;
  ready: boolean;
  detail: string;
  latency_ms?: number | null;
};

export type Health = {
  ok: boolean;
  version: string;
  default_engine: string;
  engines: string[];
  ffmpeg: boolean;
  data_dir: string;
  projects: number;
  pending_jobs: number;
};

export type EngineSettings = {
  default_engine: string;
  comfy_url: string;
  comfy_token: string;
  comfy_token_set: boolean;
  comfy_workflow: string;
  hf_space_id: string;
  hf_api_name: string;
  available_engines: EngineInfo[];
};
