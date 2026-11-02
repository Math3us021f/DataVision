export const AVATAR_COLORS = ["orange", "green", "blue", "violet", "rose", "amber", "teal", "slate"] as const;
export type AvatarColor = (typeof AVATAR_COLORS)[number];

export interface Me {
  username: string;
  is_admin: boolean;
  display_name: string | null;
  avatar_color: AvatarColor | null;
  /** E-mail de verificação, sempre mascarado (m***@gmail.com); null = ainda não cadastrado. */
  email_masked: string | null;
  /** Tempo sem atividade até o servidor encerrar a sessão (o navegador só avisa antes). */
  idle_timeout_seconds: number;
}

export interface Profile {
  username: string;
  is_admin: boolean;
  display_name: string | null;
  avatar_color: AvatarColor | null;
  email_masked: string | null;
  member_since: string;
  usage: { datasets: number; storage_bytes: number; profiled: number; dashboards: number };
}

export interface LoginEvent {
  success: boolean;
  browser: string;
  created_at: string;
}

export interface UploadDay {
  day: string; // AAAA-MM-DD
  count: number;
}

export interface RecentDataset {
  id: number;
  original_name: string;
  format: string;
  size_bytes: number;
  created_at: string;
}

export interface AuditEntry {
  action: string;
  details: string | null;
  created_at: string;
  actor: string | null;
  target: string | null;
}

export interface Summary {
  mine: { datasets: number; storage_bytes: number; profiled: number };
  recent_datasets: RecentDataset[];
  uploads_by_day: UploadDay[];
  admin?: {
    users: { total: number; active: number; inactive: number };
    datasets_total: number;
    recent_audit: AuditEntry[];
  };
}

export interface Dataset {
  id: number;
  original_name: string;
  format: string;
  size_bytes: number;
  created_at: string | null;
  profiled: boolean;
}

export interface TopValue {
  value: string;
  count: number;
}

export interface ColumnProfile {
  column_name: string;
  inferred_type: string;
  null_count: number;
  distinct_count: number;
  min_value: number | null;
  max_value: number | null;
  mean_value: number | null;
  median_value: number | null;
  top_values: TopValue[] | null;
  histogram: { bin_edges: number[]; counts: number[] } | null;
}

export interface DatasetProfile {
  row_count: number;
  duplicate_row_count: number;
  columns: ColumnProfile[];
}

export interface DatasetSample {
  columns: string[];
  rows: (string | null)[][];
  total_rows: number;
  sample_size: number;
}

export interface SystemMetrics {
  cpu_percent: number;
  memory: { total_bytes: number; used_bytes: number; percent: number };
}

export type ChartType = "bar" | "line" | "pie" | "kpi";
export type Agg = "sum" | "mean" | "count" | "min" | "max" | "count_distinct";
export type TimeGrain = "day" | "month" | "year";
export type FilterOp = "eq" | "ne" | "gt" | "gte" | "lt" | "lte" | "in" | "contains";
export type Scalar = string | number | boolean;

export interface FilterSpec {
  column: string;
  op: FilterOp;
  value: Scalar | Scalar[];
}

export interface QuerySpec {
  chart: ChartType;
  dimension?: { column: string; time_grain: TimeGrain | null } | null;
  metrics: { column: string; agg: Agg }[];
  filters: FilterSpec[];
  limit: number;
}

export interface QueryResult {
  categories: string[];
  series: { name: string; data: (number | null)[] }[];
  total_rows_matched: number;
  truncated: boolean;
}

export interface WidgetSuggestion {
  title: string;
  spec: QuerySpec;
}

export interface SavedDashboard {
  widgets: QuerySpec[];
  filters: FilterSpec[];
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface UserRow {
  id: number;
  username: string;
  is_admin: boolean;
  is_active: boolean;
  email_masked: string | null;
}

export interface UsersSummary {
  total: number;
  active: number;
  inactive: number;
  admins: number;
}

export interface AuditLogRow {
  id: number;
  action: string;
  details: string | null;
  created_at: string;
  actor_username: string | null;
  target_username: string | null;
}

export interface FullMetrics extends SystemMetrics {
  aviso_escopo: string;
  disk: { total_bytes: number; used_bytes: number; percent: number };
  network: { bytes_sent: number; bytes_recv: number };
}

export interface FileEntry {
  name: string;
  is_dir: boolean;
  size_bytes: number | null;
}

export interface NotificationItem {
  id: number;
  kind: string;
  message: string;
  created_at: string;
  read: boolean;
}

export interface NotificationsData {
  items: NotificationItem[];
  unread: number;
}
