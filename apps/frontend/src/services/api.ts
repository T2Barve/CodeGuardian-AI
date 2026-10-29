import {
  AuditLogListResponse,
  DashboardSummaryResponse,
  Finding,
  FixPRResponse,
  GitHubAccessibleReposResponse,
  IntegrationsStatusResponse,
  MultiAgentControlCenterResponse,
  PolicyRead,
  PullRequestAnalyzeResponse,
  PullRequestItem,
  PullRequestListResponse,
  RepositoryCreateRequest,
  RepositoryDetail,
  RepositoryRead,
  RepositorySyncResponse,
  RepositoryValidateResponse,
  ReviewReport,
  ScannerCenterResponse,
  LoginRequest,
  LogoutResponse,
  RegisterRequest,
  TokenResponse,
  UserProfile,
} from '../types';

const BASE_URL = '/api/v1';

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const token = localStorage.getItem('codeguardian_token');
  const authHeaders: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};

  const res = await fetch(url, {
    ...options,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders,
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
    try {
      const errorJson = await res.json();
      errorDetail = errorJson.detail || errorJson.title || errorDetail;
    } catch {
      // Keep default
    }
    throw new Error(errorDetail);
  }

  return res.json();
}

export const api = {
  // Authentication
  login: async (payload: LoginRequest): Promise<TokenResponse> => {
    return fetchJson<TokenResponse>(`${BASE_URL}/auth/login`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  register: async (payload: RegisterRequest): Promise<TokenResponse> => {
    return fetchJson<TokenResponse>(`${BASE_URL}/auth/register`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  logout: async (): Promise<LogoutResponse> => {
    return fetchJson<LogoutResponse>(`${BASE_URL}/auth/logout`, {
      method: 'POST',
    });
  },

  getMe: async (): Promise<UserProfile> => {
    return fetchJson<UserProfile>(`${BASE_URL}/auth/me`);
  },
  // Dashboard
  getDashboardSummary: async (): Promise<DashboardSummaryResponse> => {
    return fetchJson<DashboardSummaryResponse>(`${BASE_URL}/dashboard/summary`);
  },

  seedDemoData: async (): Promise<{ status: string; message: string }> => {
    return fetchJson<{ status: string; message: string }>(`${BASE_URL}/dashboard/seed`, {
      method: 'POST',
    });
  },

  // Repositories & Onboarding
  getRepositories: async (isActive?: boolean): Promise<RepositoryRead[]> => {
    const query = isActive !== undefined ? `?is_active=${isActive}` : '';
    return fetchJson<RepositoryRead[]>(`${BASE_URL}/repositories${query}`);
  },

  getRepositoryDetail: async (id: string): Promise<RepositoryDetail> => {
    return fetchJson<RepositoryDetail>(`${BASE_URL}/repositories/${id}`);
  },

  validateRepository: async (url: string): Promise<RepositoryValidateResponse> => {
    return fetchJson<RepositoryValidateResponse>(`${BASE_URL}/repositories/validate`, {
      method: 'POST',
      body: JSON.stringify({ url }),
    });
  },

  createRepository: async (payload: RepositoryCreateRequest): Promise<RepositoryRead> => {
    return fetchJson<RepositoryRead>(`${BASE_URL}/repositories`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  updateRepositoryMonitoring: async (
    repositoryId: string,
    isActive: boolean
  ): Promise<RepositoryRead> => {
    return fetchJson<RepositoryRead>(`${BASE_URL}/repositories/${repositoryId}/monitoring`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: isActive }),
    });
  },

  syncRepository: async (repositoryId: string): Promise<RepositorySyncResponse> => {
    return fetchJson<RepositorySyncResponse>(`${BASE_URL}/repositories/${repositoryId}/sync`, {
      method: 'POST',
    });
  },

  deleteRepository: async (repositoryId: string): Promise<{ status: string; message: string }> => {
    return fetchJson<{ status: string; message: string }>(`${BASE_URL}/repositories/${repositoryId}`, {
      method: 'DELETE',
    });
  },

  getUserGitHubRepositories: async (): Promise<GitHubAccessibleReposResponse> => {
    return fetchJson<GitHubAccessibleReposResponse>(`${BASE_URL}/repositories/github/user-repos`);
  },

  // Pull Requests
  getPullRequests: async (params?: {
    repository_id?: string;
    status?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<PullRequestListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.repository_id) searchParams.set('repository_id', params.repository_id);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return fetchJson<PullRequestListResponse>(`${BASE_URL}/pull-requests${query}`);
  },

  getPullRequestDetail: async (pullRequestId: string): Promise<PullRequestItem> => {
    return fetchJson<PullRequestItem>(`${BASE_URL}/pull-requests/${pullRequestId}`);
  },

  analyzePullRequest: async (pullRequestId: string): Promise<PullRequestAnalyzeResponse> => {
    return fetchJson<PullRequestAnalyzeResponse>(`${BASE_URL}/pull-requests/${pullRequestId}/analyze`, {
      method: 'POST',
      body: JSON.stringify({ force_rescan: true }),
    });
  },

  // Review & Reports
  getReviewReport: async (reviewRunId: string): Promise<ReviewReport> => {
    return fetchJson<ReviewReport>(`${BASE_URL}/reviews/${reviewRunId}/report`);
  },

  getReviewMarkdown: async (reviewRunId: string): Promise<string> => {
    const res = await fetch(`${BASE_URL}/reviews/${reviewRunId}/report/markdown`);
    if (!res.ok) {
      throw new Error(`Failed to fetch markdown report: ${res.statusText}`);
    }
    return res.text();
  },

  // Findings
  getAllFindings: async (params?: {
    category?: string;
    severity?: string;
    status?: string;
    repository_id?: string;
    search?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ total: number; severity_counts: Record<string, number>; items: Finding[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set('category', params.category);
    if (params?.severity) searchParams.set('severity', params.severity);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.repository_id) searchParams.set('repository_id', params.repository_id);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return fetchJson(`${BASE_URL}/findings${query}`);
  },

  getReviewFindings: async (
    reviewRunId: string,
    params?: { category?: string; severity?: string; status?: string }
  ): Promise<{ total: number; severity_counts: Record<string, number>; items: Finding[] }> => {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set('category', params.category);
    if (params?.severity) searchParams.set('severity', params.severity);
    if (params?.status) searchParams.set('status', params.status);

    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return fetchJson(`${BASE_URL}/reviews/${reviewRunId}/findings${query}`);
  },

  getFindingDetail: async (findingId: string): Promise<Finding> => {
    return fetchJson<Finding>(`${BASE_URL}/findings/${findingId}`);
  },

  updateFindingStatus: async (
    findingId: string,
    status: string,
    reason?: string
  ): Promise<Finding> => {
    return fetchJson<Finding>(`${BASE_URL}/findings/${findingId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status, reason }),
    });
  },

  // Scanners
  getScannersStatus: async (): Promise<ScannerCenterResponse> => {
    return fetchJson<ScannerCenterResponse>(`${BASE_URL}/scanners`);
  },

  // AI Multi-Agent Orchestration
  getAgentsStatus: async (): Promise<MultiAgentControlCenterResponse> => {
    return fetchJson<MultiAgentControlCenterResponse>(`${BASE_URL}/agents/status`);
  },

  getReviewAgents: async (reviewRunId: string): Promise<any[]> => {
    return fetchJson<any[]>(`${BASE_URL}/reviews/${reviewRunId}/agents`);
  },

  // Integrations
  getIntegrationsStatus: async (): Promise<IntegrationsStatusResponse> => {
    return fetchJson<IntegrationsStatusResponse>(`${BASE_URL}/integrations/status`);
  },

  // Audit Logs
  getAuditLogs: async (params?: {
    resource_type?: string;
    action?: string;
    limit?: number;
    offset?: number;
  }): Promise<AuditLogListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.resource_type) searchParams.set('resource_type', params.resource_type);
    if (params?.action) searchParams.set('action', params.action);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const query = searchParams.toString() ? `?${searchParams.toString()}` : '';
    return fetchJson<AuditLogListResponse>(`${BASE_URL}/audit/logs${query}`);
  },

  // Remediation & Fix PRs
  getFixPRs: async (status?: string): Promise<FixPRResponse[]> => {
    const query = status ? `?status=${status}` : '';
    return fetchJson<FixPRResponse[]>(`${BASE_URL}/fix-prs${query}`);
  },

  getFixPRDetail: async (id: string): Promise<FixPRResponse> => {
    return fetchJson<FixPRResponse>(`${BASE_URL}/fix-prs/${id}`);
  },

  createFixPR: async (remediationId: string): Promise<FixPRResponse> => {
    return fetchJson<FixPRResponse>(`${BASE_URL}/remediation/${remediationId}/fix-pr`, {
      method: 'POST',
    });
  },

  // Policies & RAG
  getPolicies: async (category?: string): Promise<PolicyRead[]> => {
    const query = category ? `?category=${encodeURIComponent(category)}` : '';
    return fetchJson<PolicyRead[]>(`${BASE_URL}/policies${query}`);
  },

  getPolicyDetail: async (id: string): Promise<PolicyRead> => {
    return fetchJson<PolicyRead>(`${BASE_URL}/policies/${id}`);
  },

  queryRAG: async (
    query: string,
    category?: string
  ): Promise<{ results_count: number; formatted_context: string; chunks: any[] }> => {
    return fetchJson(`${BASE_URL}/rag/query`, {
      method: 'POST',
      body: JSON.stringify({ query, category, similarity_threshold: 0.2 }),
    });
  },

  // Multilingual Finding Explanations & Audio Voice Narration
  explainFinding: async (
    findingId: string,
    language: string = 'en'
  ): Promise<any> => {
    return fetchJson(`${BASE_URL}/findings/${findingId}/explain`, {
      method: 'POST',
      body: JSON.stringify({ language, include_voice_script: true }),
    });
  },

  getFindingAudioUrl: (findingId: string, language: string = 'en'): string => {
    return `${BASE_URL}/findings/${findingId}/audio?lang=${encodeURIComponent(language)}`;
  },

  // NLP Code Optimization Engine
  optimizeCode: async (
    code: string,
    language: string = 'python',
    targetLanguageExplanation: string = 'en'
  ): Promise<any> => {
    return fetchJson(`${BASE_URL}/optimization/optimize`, {
      method: 'POST',
      body: JSON.stringify({
        code,
        language,
        target_language_explanation: targetLanguageExplanation,
      }),
    });
  },

  getOptimizationAudioUrl: (language: string = 'en'): string => {
    return `${BASE_URL}/optimization/audio?lang=${encodeURIComponent(language)}`;
  },
};

