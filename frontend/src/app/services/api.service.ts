import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';

export interface Paged<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ProfileDocument {
  id: number;
  kind: string;
  title: string;
  upload: string;
  raw_text: string;
  status: string;
  status_message: string;
  created_at: string;
  updated_at: string;
}

export interface ProfileFact {
  id: number;
  fact_type: string;
  title: string;
  statement: string;
  confidence: string;
  source_document_title: string;
  verified_by_user: boolean;
}

export interface JobSource {
  id: number;
  kind: string;
  name: string;
  config: any;
  enabled: boolean;
  last_status: string;
  last_message: string;
  job_count: number;
}

export interface JobMatch {
  id: number;
  job: number;
  score: number;
  confidence: string;
  explanation_json: any;
  missing_requirements: string[];
  supporting_facts: any[];
}

export interface JobPosting {
  id: number;
  title: string;
  company: string;
  location: string;
  remote_policy: string;
  seniority: string;
  compensation: string;
  description_text: string;
  extracted_json: any;
  source_url: string;
  application_url: string;
  status: string;
  match?: JobMatch;
}

export interface Resume {
  id: number;
  kind: string;
  title: string;
  content_markdown: string;
  content_json: any;
  parent_resume: number | null;
  target_job: number | null;
  target_job_title: string;
  validation: any;
  approved: boolean;
  created_at: string;
  updated_at: string;
}

export interface ApplicationRecord {
  id: number;
  job: number;
  job_detail: JobPosting;
  status: string;
  resume: number | null;
  resume_title: string;
  applied_at: string | null;
  follow_up_at: string | null;
  outcome: string;
  notes: string;
  contact_name: string;
  contact_email: string;
  events: any[];
  artifacts: any[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  constructor(private http: HttpClient) {}

  dashboard(): Observable<any> {
    return this.http.get(`${environment.apiBaseUrl}/dashboard/`);
  }

  strategy(): Observable<any> {
    return this.http.get(`${environment.apiBaseUrl}/strategy/`);
  }

  documents(): Observable<Paged<ProfileDocument>> {
    return this.http.get<Paged<ProfileDocument>>(`${environment.apiBaseUrl}/profile/documents/`);
  }

  createDocument(payload: FormData): Observable<ProfileDocument> {
    return this.http.post<ProfileDocument>(`${environment.apiBaseUrl}/profile/documents/`, payload);
  }

  facts(params: Record<string, string> = {}): Observable<Paged<ProfileFact>> {
    return this.http.get<Paged<ProfileFact>>(`${environment.apiBaseUrl}/profile/facts/`, { params: new HttpParams({ fromObject: params }) });
  }

  verifyFact(id: number): Observable<ProfileFact> {
    return this.http.post<ProfileFact>(`${environment.apiBaseUrl}/profile/facts/${id}/verify/`, {});
  }

  sources(): Observable<Paged<JobSource>> {
    return this.http.get<Paged<JobSource>>(`${environment.apiBaseUrl}/sources/`);
  }

  createSource(payload: Partial<JobSource>): Observable<JobSource> {
    return this.http.post<JobSource>(`${environment.apiBaseUrl}/sources/`, payload);
  }

  runSource(id: number): Observable<JobSource> {
    return this.http.post<JobSource>(`${environment.apiBaseUrl}/sources/${id}/run/`, {});
  }

  jobs(params: Record<string, string> = {}): Observable<Paged<JobPosting>> {
    return this.http.get<Paged<JobPosting>>(`${environment.apiBaseUrl}/jobs/`, { params: new HttpParams({ fromObject: params }) });
  }

  importJob(payload: { text: string; source_url?: string; source?: number | null }): Observable<JobPosting> {
    return this.http.post<JobPosting>(`${environment.apiBaseUrl}/jobs/import_job/`, payload);
  }

  recomputeJobMatch(id: number): Observable<any> {
    return this.http.post(`${environment.apiBaseUrl}/jobs/${id}/recompute_match/`, {});
  }

  createApplication(jobId: number): Observable<ApplicationRecord> {
    return this.http.post<ApplicationRecord>(`${environment.apiBaseUrl}/jobs/${jobId}/create_application/`, {});
  }

  resumes(params: Record<string, string> = {}): Observable<Paged<Resume>> {
    return this.http.get<Paged<Resume>>(`${environment.apiBaseUrl}/resumes/`, { params: new HttpParams({ fromObject: params }) });
  }

  createResume(payload: Partial<Resume>): Observable<Resume> {
    return this.http.post<Resume>(`${environment.apiBaseUrl}/resumes/`, payload);
  }

  tailorResume(job: number, canonical_resume?: number | null): Observable<Resume> {
    return this.http.post<Resume>(`${environment.apiBaseUrl}/resumes/tailor/`, { job, canonical_resume });
  }

  approveResume(id: number): Observable<Resume> {
    return this.http.post<Resume>(`${environment.apiBaseUrl}/resumes/${id}/approve/`, {});
  }

  exportResumeMarkdown(id: number): Observable<Blob> {
    return this.http.get(`${environment.apiBaseUrl}/resumes/${id}/export_markdown/`, { responseType: 'blob' });
  }

  applications(params: Record<string, string> = {}): Observable<Paged<ApplicationRecord>> {
    return this.http.get<Paged<ApplicationRecord>>(`${environment.apiBaseUrl}/applications/`, { params: new HttpParams({ fromObject: params }) });
  }

  updateApplication(id: number, payload: Partial<ApplicationRecord>): Observable<ApplicationRecord> {
    return this.http.patch<ApplicationRecord>(`${environment.apiBaseUrl}/applications/${id}/`, payload);
  }
}
