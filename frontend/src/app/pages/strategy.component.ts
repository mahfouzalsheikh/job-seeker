import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { ApiService } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Guidance</p>
          <h1>Strategy</h1>
          <p class="page-intro">Use real pipeline signals to decide where your effort will have the most impact.</p>
        </div>
        <button class="btn-secondary" type="button" (click)="load()">↻ Refresh strategy</button>
      </div>

      <div class="metric-grid">
        <div class="metric"><span class="metric-icon purple">▦</span><div><span>Applications</span><strong>{{ data?.totals?.applications || 0 }}</strong><small>Total tracked</small></div></div>
        <div class="metric"><span class="metric-icon blue">→</span><div><span>Applied</span><strong>{{ data?.totals?.applied || 0 }}</strong><small>Sent to employers</small></div></div>
        <div class="metric"><span class="metric-icon green">✦</span><div><span>Interviews</span><strong>{{ data?.totals?.interviews || 0 }}</strong><small>Active conversations</small></div></div>
        <div class="metric"><span class="metric-icon amber">↗</span><div><span>Response rate</span><strong>{{ data?.totals?.response_rate || 0 }}%</strong><small>Across applications</small></div></div>
      </div>

      <div class="two-col">
        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Next steps</p><h2>Recommendations</h2></div></div>
          <div class="list-row recommendation-row" *ngFor="let rec of data?.recommendations || []; let index = index">
            <span class="step-number">{{ index + 1 }}</span><div class="list-row-main">
              <strong>{{ rec.title }}</strong>
              <p>{{ rec.detail }}</p>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Best fit</p><h2>Top matches</h2></div></div>
          <div class="list-row" *ngFor="let match of data?.top_matches || []">
            <div>
              <strong>{{ match.title }}</strong>
              <p>{{ match.company || 'Unknown company' }}</p>
            </div>
            <span class="fit-score">{{ match.score }}<small>fit</small></span>
          </div>
          <div class="empty-state small" *ngIf="!(data?.top_matches || []).length"><span class="empty-icon">◇</span><h3>No matches yet</h3><p>Import jobs to unlock fit insights.</p></div>
        </section>
      </div>
    </section>
  `,
})
export class StrategyComponent implements OnInit {
  data: any;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.strategy().subscribe((data) => this.data = data);
  }
}
