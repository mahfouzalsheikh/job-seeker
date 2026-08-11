import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Your workbench</p>
          <h1>Good momentum starts here.</h1>
          <p class="page-intro">See what needs attention and move your search forward with one clear next step.</p>
        </div>
        <a class="btn-primary" routerLink="/matches">Review matches →</a>
      </div>

      <div class="metric-grid">
        <a class="metric" routerLink="/profile"><span class="metric-icon purple">◎</span><div><span>Profile facts</span><strong>{{ data?.profile_facts || 0 }}</strong><small>{{ data?.profile_documents || 0 }} sources</small></div></a>
        <a class="metric" routerLink="/matches"><span class="metric-icon blue">◇</span><div><span>Jobs tracked</span><strong>{{ data?.jobs || 0 }}</strong><small>{{ data?.matches || 0 }} scored</small></div></a>
        <a class="metric" routerLink="/resume-lab"><span class="metric-icon amber">▤</span><div><span>Resumes</span><strong>{{ data?.resumes || 0 }}</strong><small>Ready to tailor</small></div></a>
        <a class="metric" routerLink="/pipeline"><span class="metric-icon green">▦</span><div><span>Applications</span><strong>{{ data?.applications || 0 }}</strong><small>{{ data?.strategy?.totals?.interviews || 0 }} interviews</small></div></a>
      </div>

      <div class="dashboard-grid">
        <section class="panel action-panel">
          <div class="panel-head"><div><p class="eyebrow">Priorities</p><h2>Recommended next actions</h2></div><a class="text-link" routerLink="/strategy">View strategy →</a></div>
          <div class="action-list">
            <div class="list-row recommendation-row" *ngFor="let rec of data?.strategy?.recommendations || []; let index = index">
              <span class="step-number">{{ index + 1 }}</span>
              <div class="list-row-main">
                <strong>{{ rec.title }}</strong>
                <p>{{ rec.detail }}</p>
              </div>
            </div>
          </div>
          <div class="empty-state small" *ngIf="!(data?.strategy?.recommendations || []).length"><span class="empty-icon">✓</span><h3>You’re all caught up</h3><p>New recommendations will appear as your search evolves.</p></div>
        </section>

        <section class="panel pipeline-health">
          <div class="panel-head"><div><p class="eyebrow">Progress</p><h2>Pipeline health</h2></div><a class="text-link" routerLink="/pipeline">Open board →</a></div>
          <div class="status-grid">
            <div *ngFor="let status of statusKeys()">
              <span>{{ statusLabel(status) }}</span>
              <strong>{{ data.strategy.by_status[status] }}</strong>
              <span class="status-bar"><i [style.width.%]="statusShare(status)"></i></span>
            </div>
          </div>
          <div class="empty-state small" *ngIf="!statusKeys().length"><span class="empty-icon">▦</span><h3>Your pipeline is ready</h3><p>Create an application from a job match to start tracking progress.</p></div>
        </section>
      </div>

      <section class="quick-start">
        <div><span class="quick-icon">1</span><div><strong>Build your profile</strong><p>Add career evidence</p></div></div><span>→</span>
        <div><span class="quick-icon">2</span><div><strong>Score opportunities</strong><p>Import job descriptions</p></div></div><span>→</span>
        <div><span class="quick-icon">3</span><div><strong>Tailor and apply</strong><p>Create focused materials</p></div></div>
      </section>
    </section>
  `,
})
export class DashboardComponent implements OnInit {
  data: any;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.api.dashboard().subscribe((data) => this.data = data);
  }

  statusKeys(): string[] {
    return Object.keys(this.data?.strategy?.by_status || {});
  }

  statusShare(status: string): number {
    const total = Math.max(1, this.data?.applications || 0);
    return Math.min(100, ((this.data?.strategy?.by_status?.[status] || 0) / total) * 100);
  }

  statusLabel(status: string): string {
    return status.replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase());
  }
}
