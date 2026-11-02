export interface Me {
  username: string;
  is_admin: boolean;
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

export interface SystemMetrics {
  cpu_percent: number;
  memory: { total_bytes: number; used_bytes: number; percent: number };
}
