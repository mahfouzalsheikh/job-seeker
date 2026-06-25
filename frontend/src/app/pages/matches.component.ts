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
          <p class="eyebrow">Discovery</p>
          <h1>Matches</h1>
        </div>
        <button class="btn-primary" type="button" (click)="load()">Refresh</button>
      </div>

      <section class="panel">
        <h2>Import Job</h2>
        <div class="import-grid">
          <label>
            Source URL
            <input name="sourceUrl" [(ngModel)]="sourceUrl" placeholder="https://company.example/jobs/123">
          </label>
          <label>
            Job description
            <textarea name="jobText" rows="8" [(ngModel)]="jobText"></textarea>
          </label>
        </div>
        <button class="btn-primary" type="button" (click)="importJob()" [disabled]="!jobText.trim()">Extract and Rank</button>
        <span class="muted">{{ message }}</span>
      </section>

      <div class="workspace-grid">
        <section class="panel">
          <div class="panel-head">
            <h2>Job List</h2>
            <div class="filter-row">
              <input class="compact-input" placeholder="Search" [(ngModel)]="search" (keyup.enter)="load()">
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
              <small>{{ job.company || 'Unknown company' }} · {{ job.remote_policy }}</small>
            </span>
            <span class="fit-score">{{ job.match?.score || 0 }}</span>
          </button>
        </section>

        <section class="panel detail-panel" *ngIf="selected; else emptyState">
          <div class="panel-head">
            <div>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.company || 'Unknown company' }} · {{ selected.location || 'Location unknown' }}</p>
            </div>
            <span class="fit-badge">{{ selected.match?.score || 0 }}</span>
          </div>

          <div class="card-line">
            <span class="status-chip">{{ selected.remote_policy }}</span>
            <span class="status-chip">{{ selected.match?.confidence || 'unscored' }}</span>
            <span class="status-chip">{{ selected.seniority || 'seniority unknown' }}</span>
          </div>

          <h3>Match Explanation</h3>
          <p>{{ selected.match?.explanation_json?.summary || 'No match summary yet.' }}</p>

          <h3>Covered Skills</h3>
          <div class="chip-row">
            <span class="status-chip good" *ngFor="let skill of selected.match?.explanation_json?.covered_skills || []">{{ skill }}</span>
          </div>

          <h3>Gaps</h3>
          <div class="chip-row">
            <span class="status-chip warn" *ngFor="let gap of selected.match?.missing_requirements || []">{{ gap }}</span>
          </div>

          <h3>Evidence</h3>
          <div class="list-row" *ngFor="let fact of selected.match?.supporting_facts || []">
            <div>
              <strong>{{ fact.title }}</strong>
              <p>{{ fact.statement }}</p>
            </div>
          </div>

          <div class="action-row">
            <button class="btn-primary" type="button" (click)="tailor(selected)">Customize Resume</button>
            <button class="btn-secondary" type="button" (click)="createApplication(selected)">Create Application</button>
            <button class="btn-secondary" type="button" (click)="recompute(selected)">Recompute</button>
          </div>
        </section>

        <ng-template #emptyState>
          <section class="panel detail-panel">
            <h2>No job selected</h2>
            <p>Select a job to inspect match evidence, gaps, and application actions.</p>
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

  createApplication(job: JobPosting): void {
    this.api.createApplication(job.id).subscribe({
      next: () => this.message = 'Application created in pipeline.',
      error: () => this.message = 'Could not create application.',
    });
  }
}

