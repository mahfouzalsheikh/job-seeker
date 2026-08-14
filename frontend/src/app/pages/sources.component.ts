import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ApiService, JobSource } from '../services/api.service';
import { RealtimeService } from '../services/realtime.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Discovery</p>
          <h1>A quiet, reliable discovery engine.</h1>
          <p class="page-intro">Connect compliant feeds, refresh them on schedule, and let only fresh, eligible roles reach your inbox.</p>
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
            <textarea rows="9" [(ngModel)]="configText" name="configText"></textarea>
          </label>
          <div class="connector-help"><strong>Connector examples</strong><code>{{ '{' }}"connector":"jobicy","count":30,"geo":"canada","industry":"engineering","tag":"platform engineer"{{ '}' }}</code><code>{{ '{' }}"connector":"arbeitnow","remote_only":true,"max_results":30,"keywords":["engineering","software"]{{ '}' }}</code><code>{{ '{' }}"connector":"greenhouse","board_token":"acme","company":"Acme"{{ '}' }}</code><code>{{ '{' }}"connector":"lever","site":"acme","company":"Acme"{{ '}' }}</code><code>{{ '{' }}"connector":"ashby","board":"acme","company":"Acme"{{ '}' }}</code></div>
          <button class="btn-primary" type="button" (click)="create()" [disabled]="saving"><span class="spinner" *ngIf="saving" aria-hidden="true"></span>{{ saving ? 'Saving…' : 'Save source' }}</button>
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
            <button class="btn-mini" type="button" (click)="run(source)" [disabled]="isRunning(source)"><span class="spinner" *ngIf="isRunning(source)" aria-hidden="true"></span>{{ isRunning(source) ? 'Running…' : 'Run' }}</button>
          </div>
          <div class="empty-state small" *ngIf="!sources.length"><span class="empty-icon">⌁</span><h3>No sources configured</h3><p>Add your first source to organize job discovery.</p></div>
        </section>
      </div>
    </section>
  `,
})
export class SourcesComponent implements OnInit, OnDestroy {
  sources: JobSource[] = [];
  name = 'Manual Imports';
  kind = 'manual';
  configText = '{}';
  message = '';
  saving = false;
  runningSourceIds = new Set<number>();
  private eventSub?: Subscription;

  constructor(private api: ApiService, private realtime: RealtimeService) {}

  ngOnInit(): void {
    this.load();
    this.eventSub = this.realtime.events$.subscribe((event) => {
      if (event.type === 'source_run_finished') {
        this.runningSourceIds.delete(Number(event.source_id));
        this.runningSourceIds = new Set(this.runningSourceIds);
        this.message = `Source refresh finished: ${event.imported || 0} new, ${event.updated || 0} updated.`;
        this.load();
      }
    });
  }

  ngOnDestroy(): void { this.eventSub?.unsubscribe(); }

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
    this.saving = true;
    this.api.createSource({ name: this.name, kind: this.kind, config, enabled: true }).subscribe({
      next: () => {
        this.saving = false;
        this.message = 'Source saved.';
        this.load();
      },
      error: () => { this.saving = false; this.message = 'Could not save source.'; },
    });
  }

  run(source: JobSource): void {
    if (this.isRunning(source)) return;
    this.runningSourceIds.add(source.id);
    this.runningSourceIds = new Set(this.runningSourceIds);
    source.last_status = 'queued';
    source.last_message = 'Discovery refresh queued.';
    this.api.runSource(source.id).subscribe({
      next: () => this.message = `${source.name} is refreshing in the background. You can leave this page.`,
      error: () => { this.runningSourceIds.delete(source.id); this.runningSourceIds = new Set(this.runningSourceIds); this.message = `${source.name} could not be refreshed.`; },
    });
  }

  isRunning(source: JobSource): boolean { return this.runningSourceIds.has(source.id) || ['queued', 'running'].includes(source.last_status); }
}
