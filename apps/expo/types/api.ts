export interface ConfigModel {
  resolver_url: string;
  strm_output_path: string;
  tmdb_api_key: string | null;
  html_title_fetch: boolean;
}

export interface SetupRequest extends ConfigModel {
  run_initial_job: boolean;
  initial_job_type: string;
  initial_job_payload?: Record<string, unknown> | null;
}

export interface QueueHealthStatus {
  status: "ok" | "error";
  detail?: string | null;
}

export interface HealthStatus {
  status: "ok";
  version: string;
  queue: QueueHealthStatus;
}

export interface JobModel {
  id: string;
  type: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  progress: number;
  worker_id?: string | null;
  payload?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  error_message?: string | null;
  duration_seconds?: number | null;
}

export interface JobMetricsModel {
  total: number;
  status_counts: Record<string, number>;
  type_counts: Record<string, number>;
  average_duration_seconds: number | null;
  last_finished_at: string | null;
  queue_depth: number;
}

export interface SetupResponse {
  config: ConfigModel;
  job: JobModel | null;
}

export interface StreamVariantModel {
  source: string;
  quality: string;
  url: string;
}

export type LibraryItemType = "movie" | "episode";

export interface LibraryItemModel {
  id: string;
  title: string;
  item_type: LibraryItemType;
  site: string;
  year: number | null;
  tmdb_id: string | null;
  variants: StreamVariantModel[];
}

export interface LibraryListModel {
  items: LibraryItemModel[];
  total: number;
  page: number;
  page_size: number;
}

export interface JobRunRequest {
  type: string;
  payload?: Record<string, unknown> | null;
}

export interface ConfigUpdate {
  resolver_url?: string | null;
  strm_output_path?: string | null;
  tmdb_api_key?: string | null;
  html_title_fetch?: boolean | null;
}
