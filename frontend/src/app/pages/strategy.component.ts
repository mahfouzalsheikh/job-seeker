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
        </div>
        <button class="btn-primary" type="button" (click)="load()">Refresh Strategy</button>
      </div>

      <div class="metric-grid">
        <div class="metric"><span>Applications</span><strong>{{ data?.totals?.applications || 0 }}</strong></div>
        <div class="metric"><span>Applied</span><strong>{{ data?.totals?.applied || 0 }}</strong></div>
        <div class="metric"><span>Interviews</span><strong>{{ data?.totals?.interviews || 0 }}</strong></div>
        <div class="metric"><span>Response rate</span><strong>{{ data?.totals?.response_rate || 0 }}%</strong></div>
      </div>

      <div class="two-col">
        <section class="panel">
          <h2>Recommendations</h2>
          <div class="list-row" *ngFor="let rec of data?.recommendations || []">
            <div>
              <strong>{{ rec.title }}</strong>
              <p>{{ rec.detail }}</p>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Top Matches</h2>
          <div class="list-row" *ngFor="let match of data?.top_matches || []">
            <div>
              <strong>{{ match.title }}</strong>
              <p>{{ match.company || 'Unknown company' }}</p>
            </div>
            <span class="fit-score">{{ match.score }}</span>
          </div>
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

