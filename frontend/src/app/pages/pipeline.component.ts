import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, ApplicationRecord } from '../services/api.service';

interface StatusDef {
  key: string;
  label: string;
}

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Application operations</p>
          <h1>Every stage should create the next useful action.</h1>
          <p class="page-intro">Track the opportunity, exact material versions, conversations, and follow-up commitments in one audit trail.</p>
        </div>
        <button class="btn-secondary" type="button" (click)="load()">↻ Refresh</button>
      </div>

      <div class="board-toolbar"><div><strong>{{ totalApplications }} opportunities</strong><span>Drag a card to update its status · select a card to open its workspace</span></div><span class="status-chip good">● Live pipeline</span></div>
      <section class="pipeline-board" aria-label="Application pipeline">
        <div class="pipeline-col" *ngFor="let status of statuses" [class.drop-target]="dropTargetStatus === status.key" (dragover)="allowDrop($event, status.key)" (dragleave)="clearDropTarget(status.key)" (drop)="dropApplication($event, status.key)">
          <div class="pipeline-col-head"><h2>{{ status.label }}</h2><span>{{ byStatus(status.key).length }}</span></div>
          <button class="application-card" type="button" *ngFor="let app of byStatus(status.key)" [class.selected]="selected?.id === app.id" [class.dragging]="draggedApplicationId === app.id" [attr.draggable]="loadingApplicationId !== app.id" (dragstart)="startDrag($event, app)" (dragend)="endDrag()" (click)="select(app)" [disabled]="loadingApplicationId === app.id">
            <strong>{{ app.job_detail.title }}</strong>
            <p>{{ app.job_detail.company || 'Unknown company' }} · {{ app.job_detail.location || app.job_detail.remote_policy }}</p>
            <div class="card-chip-row"><span class="status-chip" [class.good]="app.job_detail.match?.meets_profile_threshold">{{ app.job_detail.match?.normalized_score || 0 }} calibrated · {{ app.job_detail.match?.score || 0 }} raw</span><span class="status-chip" [class.good]="app.job_detail.match?.hard_filter_status === 'pass'">{{ app.job_detail.match?.hard_filter_status || 'unreviewed' }}</span></div>
            <div class="application-card-footer"><span>{{ app.resume_title || 'No resume linked' }}</span><span>{{ app.artifact_count || 0 }} files · {{ app.updated_at | date:'MMM d' }} →</span></div>
          </button>
          <div class="column-empty" *ngIf="!byStatus(status.key).length">No applications</div>
        </div>
      </section>
      <p class="board-status" role="status" aria-live="polite">{{ boardMessage }}</p>
      <nav class="pagination" *ngIf="pageCount > 1" aria-label="Application pages">
        <button class="btn-secondary" type="button" (click)="goToPage(currentPage - 1)" [disabled]="currentPage === 1">← Newer</button>
        <span>Page {{ currentPage }} of {{ pageCount }}</span>
        <button class="btn-secondary" type="button" (click)="goToPage(currentPage + 1)" [disabled]="currentPage === pageCount">Older →</button>
      </nav>

      <div class="application-modal-backdrop" *ngIf="selected" (click)="closeSelected()" (keydown.escape)="closeSelected()">
      <section class="panel application-detail" role="dialog" aria-modal="true" aria-label="Application workspace" tabindex="-1" (click)="$event.stopPropagation()">
        <div class="panel-head">
          <div>
            <h2>{{ selected.job_detail.title }}</h2>
            <p>{{ selected.job_detail.company || 'Unknown company' }} · {{ selected.job_detail.location || 'Location unknown' }}</p>
          </div>
          <div class="modal-head-actions"><span class="fit-badge" [class.good]="selected.job_detail.match?.meets_profile_threshold">{{ selected.job_detail.match?.normalized_score || 0 }}<small>calibrated · {{ selected.job_detail.match?.score || 0 }} raw</small></span><button class="icon-button" type="button" (click)="closeSelected()" aria-label="Close application workspace">×</button></div>
        </div>

        <div class="edit-grid">
          <label>
            Status
            <select [(ngModel)]="selected.status" name="status">
              <option *ngFor="let status of statuses" [value]="status.key">{{ status.label }}</option>
            </select>
          </label>
          <label>
            Follow-up
            <input type="datetime-local" [(ngModel)]="followUpLocal" name="followUpLocal">
          </label>
          <label>
            Contact name
            <input [(ngModel)]="selected.contact_name" name="contactName">
          </label>
          <label>
            Contact email
            <input [(ngModel)]="selected.contact_email" name="contactEmail">
          </label>
        </div>

        <label>
          Notes
          <textarea rows="5" [(ngModel)]="selected.notes" name="notes"></textarea>
        </label>

        <div class="action-row">
            <button class="btn-primary" type="button" (click)="saveSelected()" [disabled]="saving"><span class="spinner" *ngIf="saving" aria-hidden="true"></span>{{ saving ? 'Saving…' : 'Save' }}</button>
            <button class="btn-secondary" type="button" (click)="requestRender()" *ngIf="selected.resume" [disabled]="requestingRender"><span class="spinner" *ngIf="requestingRender" aria-hidden="true"></span>{{ requestingRender ? 'Requesting…' : 'Render PDF bundle' }}</button>
            <span class="muted">{{ message }}</span>
        </div>

        <div class="section-divider"><span>Application materials</span></div>
        <section class="material-downloads" aria-label="Application materials">
          <article *ngIf="selected.resume_detail">
            <span class="material-icon">R</span>
            <div><strong>{{ selected.resume_detail.title }}</strong><small>Resume · {{ selected.resume_detail.approved ? 'approved' : 'draft' }}</small></div>
            <div class="material-actions"><button class="btn-mini" type="button" (click)="downloadResume(selected.resume_detail, 'markdown')">Download .md</button><button class="btn-mini" type="button" (click)="downloadResume(selected.resume_detail, 'pdf')">Download PDF</button></div>
          </article>
          <article *ngFor="let letter of selected.cover_letters">
            <span class="material-icon letter">CL</span>
            <div><strong>{{ letter.title }}</strong><small>Cover letter · version {{ letter.version }} · {{ letter.approved ? 'approved' : 'draft' }}</small></div>
            <div class="material-actions"><button class="btn-mini" type="button" (click)="downloadLetter(letter, 'markdown')">Download .md</button><button class="btn-mini" type="button" (click)="downloadLetter(letter, 'pdf')">Download PDF</button></div>
          </article>
          <article *ngFor="let artifact of selected.artifacts">
            <span class="material-icon">↓</span>
            <div><strong>{{ artifact.title }}</strong><small>{{ artifact.kind.replaceAll('_', ' ') }}</small></div>
            <div class="material-actions"><button class="btn-mini" type="button" (click)="downloadArtifact(artifact)">Download</button></div>
          </article>
          <p class="muted" *ngIf="!selected.resume_detail && !selected.cover_letters.length && !selected.artifacts.length">No materials are linked to this application yet.</p>
        </section>

        <div class="section-divider"><span>Activity</span></div>
        <div class="timeline">
          <div class="timeline-item" *ngFor="let event of selected.events">
            <span class="timeline-dot"></span><div>
            <strong>{{ event.event_type }}</strong>
            <p>{{ event.notes }} · {{ event.happened_at | date:'short' }}</p>
            </div>
          </div>
          <p class="muted" *ngIf="!selected.events.length">No activity recorded yet.</p>
        </div>
      </section>
      </div>
    </section>
  `,
})
export class PipelineComponent implements OnInit {
  applications: ApplicationRecord[] = [];
  totalApplications = 0;
  currentPage = 1;
  readonly pageSize = 40;
  selected?: ApplicationRecord;
  loadingApplicationId: number | null = null;
  followUpLocal = '';
  message = '';
  saving = false;
  requestingRender = false;
  draggedApplicationId: number | null = null;
  dropTargetStatus: string | null = null;
  boardMessage = '';
  private ignoreNextCardClick = false;
  statuses: StatusDef[] = [
    { key: 'review', label: 'Review' },
    { key: 'discovered', label: 'Discovered' },
    { key: 'saved', label: 'Saved' },
    { key: 'approved', label: 'Approved' },
    { key: 'preparing', label: 'Preparing' },
    { key: 'materials_ready', label: 'Materials Ready' },
    { key: 'resume_ready', label: 'Resume Ready' },
    { key: 'applied', label: 'Applied' },
    { key: 'follow_up_due', label: 'Follow-Up Due' },
    { key: 'recruiter_screen', label: 'Recruiter Screen' },
    { key: 'technical_screen', label: 'Technical Screen' },
    { key: 'onsite_final', label: 'Onsite / Final' },
    { key: 'offer', label: 'Offer' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'archived', label: 'Archived' },
  ];

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.applications({ page: String(this.currentPage) }).subscribe((page) => {
      this.applications = page.results;
      this.totalApplications = page.count;
      if (this.selected && !this.applications.some((item) => item.id === this.selected?.id)) this.closeSelected();
    });
  }

  get pageCount(): number { return Math.max(1, Math.ceil(this.totalApplications / this.pageSize)); }

  goToPage(page: number): void {
    if (page < 1 || page > this.pageCount || page === this.currentPage) return;
    this.currentPage = page;
    this.selected = undefined;
    this.load();
  }

  byStatus(status: string): ApplicationRecord[] {
    return this.applications.filter((app) => app.status === status);
  }

  select(application: ApplicationRecord): void {
    if (this.ignoreNextCardClick) {
      this.ignoreNextCardClick = false;
      return;
    }
    if (this.loadingApplicationId) return;
    this.loadingApplicationId = application.id;
    this.api.application(application.id).subscribe({
      next: (detail) => { this.selected = detail; this.syncFollowUpLocal(); this.loadingApplicationId = null; },
      error: () => { this.message = 'Could not open that application. Please try again.'; this.loadingApplicationId = null; },
    });
  }

  startDrag(event: DragEvent, application: ApplicationRecord): void {
    if (!event.dataTransfer || this.loadingApplicationId) {
      event.preventDefault();
      return;
    }
    this.draggedApplicationId = application.id;
    this.boardMessage = `Moving ${application.job_detail.title}.`;
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', String(application.id));
  }

  endDrag(): void {
    this.draggedApplicationId = null;
    this.dropTargetStatus = null;
    // Browsers often emit a click after a native drag. Do not open the card then.
    this.ignoreNextCardClick = true;
    setTimeout(() => { this.ignoreNextCardClick = false; }, 250);
  }

  allowDrop(event: DragEvent, status: string): void {
    if (!this.draggedApplicationId) return;
    event.preventDefault();
    event.dataTransfer!.dropEffect = 'move';
    this.dropTargetStatus = status;
  }

  clearDropTarget(status: string): void {
    if (this.dropTargetStatus === status) this.dropTargetStatus = null;
  }

  dropApplication(event: DragEvent, targetStatus: string): void {
    event.preventDefault();
    const applicationId = Number(event.dataTransfer?.getData('text/plain')) || this.draggedApplicationId;
    const application = this.applications.find((item) => item.id === applicationId);
    this.draggedApplicationId = null;
    this.dropTargetStatus = null;
    if (!application || application.status === targetStatus || this.loadingApplicationId) return;

    const previousStatus = application.status;
    application.status = targetStatus;
    this.loadingApplicationId = application.id;
    this.boardMessage = `Updating ${application.job_detail.title}…`;
    this.api.updateApplication(application.id, { status: targetStatus }).subscribe({
      next: (updated) => {
        Object.assign(application, updated, { artifact_count: application.artifact_count });
        if (this.selected?.id === application.id) this.selected.status = updated.status;
        this.loadingApplicationId = null;
        const label = this.statuses.find((status) => status.key === targetStatus)?.label || targetStatus;
        this.boardMessage = `${application.job_detail.title} moved to ${label}.`;
      },
      error: (error) => {
        application.status = previousStatus;
        this.loadingApplicationId = null;
        this.boardMessage = error?.error?.status?.[0] || error?.error?.detail || 'Could not update the application status. Please try again.';
      },
    });
  }

  closeSelected(): void { this.selected = undefined; this.followUpLocal = ''; this.message = ''; }

  syncFollowUpLocal(): void {
    if (!this.selected?.follow_up_at) {
      this.followUpLocal = '';
      return;
    }
    this.followUpLocal = this.selected.follow_up_at.slice(0, 16);
  }

  saveSelected(): void {
    if (!this.selected) return;
    this.saving = true;
    const payload: Partial<ApplicationRecord> = {
      status: this.selected.status,
      notes: this.selected.notes,
      contact_name: this.selected.contact_name,
      contact_email: this.selected.contact_email,
      follow_up_at: this.followUpLocal ? new Date(this.followUpLocal).toISOString() : null,
    };
    this.api.updateApplication(this.selected.id, payload).subscribe((updated) => {
      this.message = 'Application saved.';
      this.selected = updated;
      this.syncFollowUpLocal();
      this.load();
      this.saving = false;
    }, () => { this.saving = false; this.message = 'Could not save the application.'; });
  }

  requestRender(): void {
    if (!this.selected) return;
    this.requestingRender = true;
    this.api.requestRender(this.selected.id).subscribe({
      next: () => { this.requestingRender = false; this.message = 'PDF rendering approval is waiting in Concierge.'; },
      error: (error) => { this.requestingRender = false; this.message = error?.error?.detail || 'Could not request PDF rendering.'; },
    });
  }

  downloadResume(resume: NonNullable<ApplicationRecord['resume_detail']>, format: 'markdown' | 'pdf'): void {
    const download = format === 'pdf' ? this.api.exportResumePdf(resume.id) : this.api.exportResumeMarkdown(resume.id);
    download.subscribe((blob) => this.saveBlob(blob, `${this.slug(resume.title)}.${format === 'pdf' ? 'pdf' : 'md'}`));
  }

  downloadLetter(letter: any, format: 'markdown' | 'pdf'): void {
    const download = format === 'pdf' ? this.api.exportCoverLetterPdf(letter.id) : this.api.exportCoverLetterMarkdown(letter.id);
    download.subscribe((blob) => this.saveBlob(blob, `${this.slug(letter.title)}.${format === 'pdf' ? 'pdf' : 'md'}`));
  }

  downloadArtifact(artifact: any): void {
    this.api.downloadArtifact(artifact.id).subscribe((blob) => this.saveBlob(blob, artifact.title));
  }

  private saveBlob(blob: Blob, filename: string): void {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = filename; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  }

  private slug(value: string): string { return value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'application-material'; }
}
