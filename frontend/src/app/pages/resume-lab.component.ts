import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, JobPosting, Resume } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Application Materials</p>
          <h1>Resume Lab</h1>
        </div>
        <button class="btn-primary" type="button" (click)="load()">Refresh</button>
      </div>

      <div class="two-col">
        <section class="panel">
          <h2>Create Canonical Resume</h2>
          <label>
            Title
            <input [(ngModel)]="newTitle" name="newTitle">
          </label>
          <label>
            Markdown
            <textarea rows="10" [(ngModel)]="newMarkdown" name="newMarkdown"></textarea>
          </label>
          <button class="btn-primary" type="button" (click)="createCanonical()">Save Canonical</button>
          <p class="muted">{{ message }}</p>
        </section>

        <section class="panel">
          <h2>Generate Tailored Resume</h2>
          <label>
            Target job
            <select [(ngModel)]="targetJobId" name="targetJobId">
              <option [ngValue]="null">Select a job</option>
              <option *ngFor="let job of jobs" [ngValue]="job.id">{{ job.title }} · {{ job.company }}</option>
            </select>
          </label>
          <button class="btn-primary" type="button" (click)="tailor()" [disabled]="!targetJobId">Generate Draft</button>
        </section>
      </div>

      <div class="workspace-grid">
        <section class="panel">
          <h2>Resumes</h2>
          <button
            class="job-row"
            type="button"
            *ngFor="let resume of resumes"
            [class.selected]="selected?.id === resume.id"
            (click)="selected = resume">
            <span>
              <strong>{{ resume.title }}</strong>
              <small>{{ resume.kind }} · {{ resume.target_job_title || 'no target' }}</small>
            </span>
            <span class="status-chip" [class.good]="resume.approved">{{ resume.approved ? 'approved' : 'draft' }}</span>
          </button>
        </section>

        <section class="panel detail-panel" *ngIf="selected">
          <div class="panel-head">
            <div>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.kind }} · {{ selected.target_job_title || 'Canonical' }}</p>
            </div>
            <span class="status-chip" [class.good]="selected.approved">{{ selected.approved ? 'approved' : 'draft' }}</span>
          </div>

          <div class="validation-grid">
            <div>
              <span>Covered keywords</span>
              <strong>{{ (selected.validation?.keyword_coverage || []).length }}</strong>
            </div>
            <div>
              <span>Unsupported claims</span>
              <strong>{{ (selected.validation?.unsupported_claims || []).length }}</strong>
            </div>
            <div>
              <span>Weak claims</span>
              <strong>{{ (selected.validation?.weak_claims || []).length }}</strong>
            </div>
          </div>

          <h3>Risk Notes</h3>
          <div class="chip-row">
            <span class="status-chip warn" *ngFor="let note of selected.validation?.risk_notes || []">{{ note }}</span>
          </div>

          <h3>Resume Markdown</h3>
          <pre class="resume-preview">{{ selected.content_markdown }}</pre>

          <div class="action-row">
            <button class="btn-primary" type="button" (click)="approve(selected)" *ngIf="!selected.approved">Approve</button>
            <button class="btn-secondary" type="button" (click)="download(selected)">Export Markdown</button>
          </div>
        </section>
      </div>
    </section>
  `,
})
export class ResumeLabComponent implements OnInit {
  resumes: Resume[] = [];
  jobs: JobPosting[] = [];
  selected?: Resume;
  targetJobId: number | null = null;
  newTitle = 'Canonical Resume';
  newMarkdown = '';
  message = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.resumes().subscribe((page) => {
      this.resumes = page.results;
      if (!this.selected && this.resumes.length) {
        this.selected = this.resumes[0];
      }
    });
    this.api.jobs().subscribe((page) => this.jobs = page.results);
  }

  createCanonical(): void {
    this.api.createResume({
      kind: 'canonical',
      title: this.newTitle,
      content_markdown: this.newMarkdown,
      content_json: {},
    }).subscribe((resume) => {
      this.message = 'Canonical resume saved.';
      this.selected = resume;
      this.load();
    });
  }

  tailor(): void {
    if (!this.targetJobId) return;
    this.message = 'Generating tailored resume.';
    this.api.tailorResume(this.targetJobId).subscribe((resume) => {
      this.message = 'Tailored resume created.';
      this.selected = resume;
      this.load();
    });
  }

  approve(resume: Resume): void {
    this.api.approveResume(resume.id).subscribe((updated) => {
      this.selected = updated;
      this.load();
    });
  }

  download(resume: Resume): void {
    this.api.exportResumeMarkdown(resume.id).subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${resume.title.toLowerCase().replaceAll(' ', '-')}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
    });
  }
}

