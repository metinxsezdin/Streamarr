export interface ConfigModel {
  resolver_url: string;
  strm_output_path: string;
  tmdb_api_key: string | null;
  html_title_fetch: boolean;
}

export interface SetupRequest extends Omit<ConfigModel, "strm_output_path"> {
  strm_output_path?: string | null;
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

export type JobStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface JobModel {
  id: string;
  type: string;
  status: JobStatus;
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

export type LibrarySortOption =
  | "updated_desc"
  | "updated_asc"
  | "title_asc"
  | "title_desc"
  | "year_desc"
  | "year_asc";

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

export interface LibraryMetricsModel {
  total: number;
  site_counts: Record<string, number>;
  type_counts: Record<string, number>;
  tmdb_enriched: number;
  tmdb_missing: number;
}

export interface JobRunRequest {
  type: string;
  payload?: Record<string, unknown> | null;
}

export interface JobCancelRequest {
  reason?: string | null;
}

export interface ConfigUpdate {
  resolver_url?: string | null;
  strm_output_path?: string | null;
  tmdb_api_key?: string | null;
  html_title_fetch?: boolean | null;
}

export interface JobLogModel {
  id: number;
  job_id: string;
  level: "debug" | "info" | "warning" | "error";
  message: string;
  context?: Record<string, unknown> | null;
  created_at: string;
}
