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
          <p class="eyebrow">Workbench</p>
          <h1>Dashboard</h1>
        </div>
        <a class="btn-primary" routerLink="/matches">Review matches</a>
      </div>

      <div class="metric-grid">
        <div class="metric"><span>Profile facts</span><strong>{{ data?.profile_facts || 0 }}</strong></div>
        <div class="metric"><span>Jobs</span><strong>{{ data?.jobs || 0 }}</strong></div>
        <div class="metric"><span>Matches</span><strong>{{ data?.matches || 0 }}</strong></div>
        <div class="metric"><span>Applications</span><strong>{{ data?.applications || 0 }}</strong></div>
      </div>

      <div class="two-col">
        <section class="panel">
          <h2>Recommended Next Actions</h2>
          <div class="list-row" *ngFor="let rec of data?.strategy?.recommendations || []">
            <div>
              <strong>{{ rec.title }}</strong>
              <p>{{ rec.detail }}</p>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Pipeline Health</h2>
          <div class="status-grid">
            <div *ngFor="let status of statusKeys()">
              <span>{{ status }}</span>
              <strong>{{ data.strategy.by_status[status] }}</strong>
            </div>
          </div>
        </section>
      </div>
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
}

