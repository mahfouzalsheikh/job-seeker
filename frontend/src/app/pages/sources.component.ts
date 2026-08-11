import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, JobSource } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Discovery</p>
          <h1>Sources</h1>
          <p class="page-intro">Manage where opportunities enter your workspace.</p>
        </div>
        <button class="btn-secondary" type="button" (click)="load()">↻ Refresh</button>
      </div>

      <div class="two-col">
        <section class="panel">
          <div class="panel-head"><div><h2>Add a source</h2><p>Connect a channel for discovering opportunities.</p></div></div>
          <label>
            Name
            <input [(ngModel)]="name" name="name">
          </label>
          <label>
            Kind
            <select [(ngModel)]="kind" name="kind">
              <option value="manual">Manual</option>
              <option value="company_page">Company Page</option>
              <option value="ats">ATS</option>
              <option value="api">API</option>
              <option value="rss">RSS</option>
            </select>
          </label>
          <label>
            Configuration <span class="field-hint">JSON</span>
            <textarea rows="7" [(ngModel)]="configText" name="configText"></textarea>
          </label>
          <button class="btn-primary" type="button" (click)="create()">Save source</button>
          <p class="muted">{{ message }}</p>
        </section>

        <section class="panel">
          <div class="panel-head"><div><h2>Configured sources</h2><p>{{ sources.length }} discovery channels</p></div></div>
          <div class="list-row" *ngFor="let source of sources">
            <span class="document-icon">⌁</span>
            <div class="list-row-main">
              <strong>{{ source.name }}</strong>
              <p>{{ source.kind }} · {{ source.job_count || 0 }} jobs · {{ source.last_message || 'not run yet' }}</p>
            </div>
            <button class="btn-mini" type="button" (click)="run(source)">Run</button>
          </div>
          <div class="empty-state small" *ngIf="!sources.length"><span class="empty-icon">⌁</span><h3>No sources configured</h3><p>Add your first source to organize job discovery.</p></div>
        </section>
      </div>
    </section>
  `,
})
export class SourcesComponent implements OnInit {
  sources: JobSource[] = [];
  name = 'Manual Imports';
  kind = 'manual';
  configText = '{}';
  message = '';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.sources().subscribe((page) => this.sources = page.results);
  }

  create(): void {
    let config: any = {};
    try {
      config = JSON.parse(this.configText || '{}');
    } catch {
      this.message = 'Config JSON is invalid.';
      return;
    }
    this.api.createSource({ name: this.name, kind: this.kind, config, enabled: true }).subscribe({
      next: () => {
        this.message = 'Source saved.';
        this.load();
      },
      error: () => this.message = 'Could not save source.',
    });
  }

  run(source: JobSource): void {
    this.api.runSource(source.id).subscribe((updated) => {
      source.last_message = updated.last_message;
      source.last_status = updated.last_status;
    });
  }
}
