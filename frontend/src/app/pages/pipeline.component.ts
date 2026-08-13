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

      <div class="board-toolbar"><div><strong>{{ applications.length }} opportunities</strong><span>Scroll horizontally to see every stage</span></div><span class="status-chip good">● Live pipeline</span></div>
      <section class="pipeline-board" aria-label="Application pipeline">
        <div class="pipeline-col" *ngFor="let status of statuses">
          <div class="pipeline-col-head"><h2>{{ status.label }}</h2><span>{{ byStatus(status.key).length }}</span></div>
          <button class="application-card" type="button" *ngFor="let app of byStatus(status.key)" [class.selected]="selected?.id === app.id" (click)="select(app)">
            <strong>{{ app.job_detail.title }}</strong>
            <p>{{ app.job_detail.company || 'Unknown company' }}</p>
            <div class="card-line"><span class="status-chip">{{ app.job_detail.match?.score || 0 }} fit</span><span class="card-arrow">→</span></div>
          </button>
          <div class="column-empty" *ngIf="!byStatus(status.key).length">No applications</div>
        </div>
      </section>

      <section class="panel application-detail" *ngIf="selected">
        <div class="panel-head">
          <div>
            <h2>{{ selected.job_detail.title }}</h2>
            <p>{{ selected.job_detail.company || 'Unknown company' }} · {{ selected.job_detail.location || 'Location unknown' }}</p>
          </div>
          <span class="fit-badge">{{ selected.job_detail.match?.score || 0 }}<small>fit</small></span>
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
    </section>
  `,
})
export class PipelineComponent implements OnInit {
  applications: ApplicationRecord[] = [];
  selected?: ApplicationRecord;
  followUpLocal = '';
  message = '';
  saving = false;
  requestingRender = false;
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
    this.api.applications().subscribe((page) => {
      this.applications = page.results;
      if (this.selected) {
        this.selected = this.applications.find((item) => item.id === this.selected?.id);
        this.syncFollowUpLocal();
      }
    });
  }

  byStatus(status: string): ApplicationRecord[] {
    return this.applications.filter((app) => app.status === status);
  }

  select(application: ApplicationRecord): void {
    this.selected = application;
    this.syncFollowUpLocal();
  }

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
}
