import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, JobPosting } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Opportunity inbox</p>
          <h1>Decide where your effort belongs.</h1>
          <p class="page-intro">Every role is filtered for eligibility, decomposed into fit signals, and backed by your profile evidence.</p>
        </div>
        <button class="btn-primary" type="button" (click)="activeTab = 'import'">＋ Import a job</button>
      </div>

      <div class="tabs" role="tablist" aria-label="Match sections">
        <button type="button" role="tab" [class.active]="activeTab === 'matches'" [attr.aria-selected]="activeTab === 'matches'" (click)="activeTab = 'matches'">Your matches <span>{{ jobs.length }}</span></button>
        <button type="button" role="tab" [class.active]="activeTab === 'import'" [attr.aria-selected]="activeTab === 'import'" (click)="activeTab = 'import'">Import job</button>
      </div>
      <p class="feedback-banner" *ngIf="message">{{ message }}</p>

      <section class="panel import-panel" *ngIf="activeTab === 'import'">
        <div class="panel-head"><div><h2>Add a job description</h2><p>Paste the complete posting. We’ll structure it and score it against your profile.</p></div></div>
        <label>Job URL <span class="optional">Optional</span><input name="sourceUrl" [(ngModel)]="sourceUrl" placeholder="https://company.example/jobs/123"></label>
        <label>Job description<textarea name="jobText" rows="13" [(ngModel)]="jobText" placeholder="Paste the full job description here…"></textarea></label>
        <div class="action-row form-actions">
          <button class="btn-primary" type="button" (click)="importJob()" [disabled]="!jobText.trim()">Extract and rank</button>
          <button class="btn-secondary" type="button" (click)="activeTab = 'matches'">Cancel</button>
        </div>
      </section>

      <div class="workspace-grid" *ngIf="activeTab === 'matches'">
        <section class="panel matches-list-panel">
          <div class="panel-head">
            <div><h2>Ranked opportunities</h2><p>{{ jobs.length }} roles · sorted by decision value</p></div>
            <div class="filter-row">
              <div class="search-field"><span>⌕</span><input class="compact-input" aria-label="Search jobs" placeholder="Search" [(ngModel)]="search" (keyup.enter)="load()"></div>
              <select class="compact-input" [(ngModel)]="minScore" (change)="load()">
                <option value="">Any score</option>
                <option value="50">50+</option>
                <option value="70">70+</option>
                <option value="85">85+</option>
              </select>
            </div>
          </div>
          <button
            class="job-row"
            type="button"
            *ngFor="let job of jobs"
            [class.selected]="selected?.id === job.id"
            (click)="select(job)">
            <span>
              <strong>{{ job.title }}</strong>
              <small>{{ job.company || 'Unknown company' }} · {{ job.location || job.remote_policy }}</small>
              <span class="job-meta-line"><i [class.pass]="job.match?.hard_filter_status === 'pass'"></i>{{ job.match?.hard_filter_status || 'uncertain' }} eligibility · {{ job.freshness_status || 'fresh' }}</span>
            </span>
            <span class="fit-score" [class.high]="(job.match?.score || 0) >= 75">{{ job.match?.score || 0 }}<small>fit</small></span>
          </button>
          <div class="empty-state small" *ngIf="!jobs.length"><span class="empty-icon">◇</span><h3>No matching jobs yet</h3><p>Import a job description to get your first fit score.</p><button class="btn-primary" type="button" (click)="activeTab = 'import'">Import a job</button></div>
        </section>

        <section class="panel detail-panel" *ngIf="selected; else emptyState">
          <div class="panel-head">
            <div>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.company || 'Unknown company' }} · {{ selected.location || 'Location unknown' }}</p>
            </div>
            <span class="fit-badge">{{ selected.match?.score || 0 }}<small>fit</small></span>
          </div>

          <div class="card-line">
            <span class="status-chip">{{ selected.remote_policy }}</span>
            <span class="status-chip">{{ selected.match?.confidence || 'unscored' }}</span>
            <span class="status-chip">{{ selected.seniority || 'seniority unknown' }}</span>
            <span class="status-chip" [class.good]="selected.match?.hard_filter_status === 'pass'">{{ selected.match?.hard_filter_status || 'uncertain' }} eligibility</span>
          </div>

          <div class="insight-callout"><span>✦</span><div><strong>Match summary</strong><p>{{ selected.match?.explanation_json?.summary || 'No match summary yet.' }}</p></div></div>

          <h3>Why this score</h3>
          <div class="signal-breakdown">
            <div *ngFor="let signal of selected.match?.signals || []"><div><strong>{{ signal.label }}</strong><small>{{ signal.weight }}% weight</small></div><span><i [style.width.%]="signal.score"></i></span><b>{{ signal.score }}</b></div>
          </div>

          <div class="two-col detail-columns">
            <div><h3>Covered skills</h3><div class="chip-row"><span class="status-chip good" *ngFor="let skill of selected.match?.explanation_json?.covered_skills || []">{{ skill }}</span><span class="muted" *ngIf="!(selected.match?.explanation_json?.covered_skills || []).length">No covered skills identified.</span></div></div>
            <div><h3>Visible gaps</h3><div class="chip-row"><span class="status-chip warn" *ngFor="let gap of selected.match?.missing_requirements || []">{{ gap }}</span><span class="muted" *ngIf="!(selected.match?.missing_requirements || []).length">No obvious skill gaps.</span></div></div>
          </div>

          <h3>Evidence</h3>
          <div class="list-row" *ngFor="let fact of selected.match?.supporting_facts || []">
            <div>
              <strong>{{ fact.title }}</strong>
              <p>{{ fact.statement }}</p>
            </div>
          </div>

          <div class="action-row">
            <button class="btn-primary" type="button" (click)="prepare(selected)">Approve to prepare →</button>
            <button class="btn-secondary" type="button" (click)="createApplication(selected)">Save to pipeline</button>
            <button class="btn-secondary" type="button" (click)="recompute(selected)">Recompute</button>
          </div>
        </section>

        <ng-template #emptyState>
          <section class="panel detail-panel empty-state">
            <span class="empty-icon">◇</span><h2>Select an opportunity</h2>
            <p>Choose a role from the list to inspect its score, evidence, and gaps.</p>
          </section>
        </ng-template>
      </div>
    </section>
  `,
})
export class MatchesComponent implements OnInit {
  jobs: JobPosting[] = [];
  selected?: JobPosting;
  jobText = '';
  sourceUrl = '';
  search = '';
  minScore = '';
  message = '';
  activeTab: 'matches' | 'import' = 'matches';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    const params: Record<string, string> = {};
    if (this.search) params['search'] = this.search;
    if (this.minScore) params['min_score'] = this.minScore;
    this.api.jobs(params).subscribe((page) => {
      this.jobs = page.results;
      if (this.selected) {
        this.selected = this.jobs.find((job) => job.id === this.selected?.id);
      } else if (this.jobs.length) {
        this.selected = this.jobs[0];
      }
    });
  }

  select(job: JobPosting): void {
    this.selected = job;
  }

  importJob(): void {
    this.message = 'Importing and ranking job.';
    this.api.importJob({ text: this.jobText, source_url: this.sourceUrl }).subscribe({
      next: (job) => {
        this.message = 'Job imported.';
        this.jobText = '';
        this.sourceUrl = '';
        this.load();
        this.selected = job;
        this.activeTab = 'matches';
      },
      error: () => this.message = 'Import failed.',
    });
  }

  recompute(job: JobPosting): void {
    this.api.recomputeJobMatch(job.id).subscribe(() => this.message = 'Match recompute queued.');
  }

  tailor(job: JobPosting): void {
    this.message = 'Generating tailored resume.';
    this.api.tailorResume(job.id).subscribe({
      next: () => this.message = 'Tailored resume created. Open Resume Lab to review it.',
      error: () => this.message = 'Resume tailoring failed.',
    });
  }

  prepare(job: JobPosting): void {
    this.message = 'Starting the preparation workflow.';
    this.api.requestPreparation(job.id).subscribe({
      next: () => this.message = 'Approval requested. Open Concierge to review it.',
      error: () => this.message = 'Could not start the preparation workflow.',
    });
  }

  createApplication(job: JobPosting): void {
    this.api.createApplication(job.id).subscribe({
      next: () => this.message = 'Application created in pipeline.',
      error: () => this.message = 'Could not create application.',
    });
  }
}
