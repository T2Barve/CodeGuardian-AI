export interface HealthStatus {
  status: string;
  version: string;
  timestamp: string;
  environment: string;
}

export interface ReadinessStatus {
  status: string;
  database: string;
  redis: string;
  error?: string | null;
}

export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO';
export type RiskGrade = 'A' | 'B' | 'C' | 'D' | 'F';
export type FindingStatus = 'OPEN' | 'RESOLVED' | 'FALSE_POSITIVE' | 'WONT_FIX' | 'MITIGATED';

export interface CategoryRiskBreakdown {
  security: number;
  quality: number;
  testing: number;
  documentation: number;
  dependency: number;
}

export interface RecentReviewItem {
  review_run_id: string;
  job_id: string;
  repo_name: string;
  pr_number: number;
  pr_title: string;
  author: string;
  commit_sha: string;
  status: string;
  risk_score?: number | null;
  risk_grade?: RiskGrade | string | null;
  risk_level?: string | null;
  is_mergeable: boolean;
  duration_ms?: number | null;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  created_at: string;
}

export interface SecurityTrendPoint {
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface QualityTrendPoint {
  date: string;
  maintainability_score: number;
  issues_detected: number;
}

export interface DashboardSummaryResponse {
  total_repositories: number;
  total_reviews: number;
  critical_findings: number;
  high_findings: number;
  open_findings: number;
  resolved_findings: number;
  average_review_duration_ms: number;
  recent_reviews: RecentReviewItem[];
  security_trend: SecurityTrendPoint[];
  quality_trend: QualityTrendPoint[];
  category_radar: CategoryRiskBreakdown;
}

export interface FindingEvidenceRead {
  id: string;
  finding_id: string;
  source: string;
  tool: string;
  rule_id?: string | null;
  raw_message?: string | null;
  code_snippet?: string | null;
  metadata_payload?: Record<string, any>;
  created_at: string;
}

export interface Finding {
  id: string;
  review_run_id: string;
  fingerprint: string;
  category: 'SECURITY' | 'QUALITY' | 'TESTING' | 'DOCUMENTATION' | 'DEPENDENCY';
  severity: SeverityLevel;
  confidence: number;
  status: FindingStatus;
  file_path: string;
  line_start?: number | null;
  line_end?: number | null;
  title: string;
  description: string;
  impact?: string | null;
  recommendation?: string | null;
  code_snippet?: string | null;
  policy_reference?: string | null;
  evidence_count?: number;
  evidence?: FindingEvidenceRead[];
  tools_involved?: string[];
  created_at: string;
}

export interface ReportAgentSummary {
  agent_name: string;
  status: string;
  duration_ms: number;
  token_usage: number;
  findings_count: number;
  error?: string | null;
}

export interface ReviewReportSummary {
  review_run_id: string;
  job_id?: string | null;
  repo_name: string;
  pr_number: number;
  pr_title: string;
  author: string;
  commit_sha: string;
  source_branch: string;
  target_branch: string;
  risk_score: number;
  risk_grade: RiskGrade;
  risk_level: string;
  is_mergeable: boolean;
  recommended_action: string;
  duration_ms: number;
  total_findings: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  info_count: number;
}

export interface ReviewReport {
  summary: ReviewReportSummary;
  category_breakdown: CategoryRiskBreakdown;
  risk_driving_factors: string[];
  findings: Finding[];
  agent_summaries: ReportAgentSummary[];
  generated_at: string;
  markdown_content?: string | null;
}

export interface PullRequestSummary {
  id: string;
  number: number;
  title: string;
  author: string;
  source_branch: string;
  target_branch: string;
  commit_sha: string;
  status: string;
  latest_review_run_id?: string | null;
  latest_risk_score?: number | null;
  latest_risk_grade?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RepositoryRead {
  id: string;
  github_repo_id: number;
  name: string;
  owner: string;
  url: string;
  default_branch: string;
  language?: string | null;
  is_active: boolean;
  pull_requests_count: number;
  reviews_count: number;
  last_reviewed_at?: string | null;
  health_status: string;
  created_at: string;
  updated_at: string;
}

export interface RepositoryDetail extends RepositoryRead {
  recent_pull_requests: PullRequestSummary[];
}

export interface PolicyChunkRead {
  id: string;
  policy_id: string;
  chunk_index: number;
  content: string;
  embedding_reference?: string | null;
  metadata_payload?: Record<string, any>;
  created_at: string;
}

export interface PolicyRead {
  id: string;
  name: string;
  category: string;
  version: string;
  source: string;
  active: boolean;
  created_at: string;
  updated_at: string;
  chunks?: PolicyChunkRead[];
}

export type SupportedLanguageCode = 'en' | 'hi' | 'hinglish' | 'ur' | 'mr' | 'gu';

export interface FindingExplanation {
  finding_id: string;
  language: string;
  language_display_name: string;
  title: string;
  summary: string;
  root_cause: string;
  risk_impact: string;
  remediation_steps: string[];
  code_example_fix?: string | null;
  voice_script: string;
  audio_stream_url?: string | null;
}

export interface OptimizationIssue {
  issue_type: string;
  line_number?: number | null;
  description: string;
  current_complexity: string;
  target_complexity: string;
  suggestion: string;
}

export interface CodeOptimizationResult {
  is_optimized: boolean;
  original_code: string;
  optimized_code: string;
  diff: string;
  syntax_valid: boolean;
  issues: OptimizationIssue[];
  original_time_complexity: string;
  optimized_time_complexity: string;
  original_space_complexity: string;
  optimized_space_complexity: string;
  performance_improvement_factor: string;
  explanation: string;
  multilingual_explanations: Record<string, string>;
  voice_script: string;
  audio_stream_url?: string | null;
}

// Repository Onboarding
export interface RepositoryValidateRequest {
  url: string;
}

export interface RepositoryValidateResponse {
  owner: string;
  name: string;
  full_name: string;
  url: string;
  default_branch: string;
  language?: string | null;
  description?: string | null;
  is_private: boolean;
  open_issues_count: number;
  open_pull_requests_count: number;
  stargazers_count?: number;
  forks_count?: number;
  exists_in_database: boolean;
  monitoring_status: string;
  webhook_url: string;
}

export interface RepositoryCreateRequest {
  url: string;
  is_active?: boolean;
  auto_sync_prs?: boolean;
  default_branch?: string;
  language?: string;
  github_repo_id?: number;
}

export interface RepositorySyncResponse {
  repository_id: string;
  synced_pull_requests_count: number;
  pull_requests: PullRequestSummary[];
  message: string;
}

export interface GitHubAccessibleRepo {
  id?: number;
  name: string;
  full_name: string;
  owner: string;
  url?: string;
  default_branch: string;
  is_private: boolean;
  language?: string | null;
  description?: string | null;
}

export interface GitHubAccessibleReposResponse {
  configured: boolean;
  total: number;
  repositories: GitHubAccessibleRepo[];
  message?: string | null;
}

// Pull Requests
export interface PullRequestItem {
  id: string;
  repository_id: string;
  repo_name: string;
  repo_owner: string;
  number: number;
  title: string;
  author: string;
  source_branch: string;
  target_branch: string;
  commit_sha: string;
  status: string;
  latest_review_run_id?: string | null;
  latest_risk_score?: number | null;
  latest_risk_grade?: string | null;
  is_mergeable: boolean;
  findings_count: number;
  created_at: string;
  updated_at: string;
}

export interface PullRequestListResponse {
  total: number;
  items: PullRequestItem[];
}

export interface PullRequestAnalyzeResponse {
  status: string;
  job_id: string;
  pull_request_id: string;
  message: string;
}

// Scanner Center
export interface ScannerToolInfo {
  name: string;
  display_name: string;
  category: string;
  is_enabled: boolean;
  is_operational: boolean;
  description: string;
  version_command: string;
  supported_coverage: string[];
  total_detections: number;
  last_status: string;
}

export interface ScannerCenterResponse {
  total_tools: number;
  operational_tools: number;
  tools: ScannerToolInfo[];
}

// AI Multi-Agent Fabric
export interface AgentStatusInfo {
  name: string;
  display_name: string;
  role: string;
  status: string;
  total_runs: number;
  avg_duration_ms: number;
  total_tokens: number;
  discovered_findings: number;
  provider: string;
  model: string;
}

export interface MultiAgentControlCenterResponse {
  is_orchestration_active: boolean;
  active_jobs_count: number;
  total_agent_executions: number;
  total_tokens_consumed: number;
  agents: AgentStatusInfo[];
}

// Integrations
export interface IntegrationComponentStatus {
  id: string;
  name: string;
  category: string;
  status: string;
  details: string;
  is_required: boolean;
  metadata: Record<string, string>;
}

export interface IntegrationsStatusResponse {
  all_ready: boolean;
  components: IntegrationComponentStatus[];
}

// Audit Logs
export interface AuditLogRead {
  id: string;
  actor: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata_payload: Record<string, any>;
  timestamp: string;
}

export interface AuditLogListResponse {
  total: number;
  items: AuditLogRead[];
}

// Remediation Fix PRs
export interface FixPRResponse {
  id: string;
  remediation_attempt_id: string;
  finding_id: string;
  repo_name: string;
  github_pr_id?: number | null;
  number?: number | null;
  url?: string | null;
  branch_name: string;
  base_branch: string;
  status: string;
  created_at: string;
}

// Authentication & Users
export interface UserProfile {
  id: string;
  username: string;
  email?: string | null;
  avatar_url?: string | null;
  role: string;
  permissions: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  email?: string;
  role?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: UserProfile;
}

export interface LogoutResponse {
  status: string;
  message: string;
}

