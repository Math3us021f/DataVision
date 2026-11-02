export const AVATAR_COLORS = ["orange", "green", "blue", "violet", "rose", "amber", "teal", "slate"] as const;
export type AvatarColor = (typeof AVATAR_COLORS)[number];

export interface Me {
  username: string;
  is_admin: boolean;
  display_name: string | null;
  avatar_color: AvatarColor | null;
}

export interface Profile {
  username: string;
  is_admin: boolean;
  display_name: string | null;
  avatar_color: AvatarColor | null;
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
