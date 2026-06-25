import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, ProfileDocument, ProfileFact } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Knowledge Base</p>
          <h1>Profile</h1>
        </div>
        <button class="btn-primary" type="button" (click)="load()">Refresh</button>
      </div>

      <div class="two-col">
        <section class="panel">
          <h2>Add Source Material</h2>
          <form class="stack" (ngSubmit)="createDocument()">
            <label>
              Type
              <select name="kind" [(ngModel)]="kind">
                <option value="resume">Resume</option>
                <option value="note">Note</option>
                <option value="conversation">Conversation</option>
                <option value="project">Project</option>
                <option value="review">Review</option>
              </select>
            </label>
            <label>
              Title
              <input name="title" [(ngModel)]="title">
            </label>
            <label>
              File
              <input type="file" (change)="onFile($event)">
            </label>
            <label>
              Raw text
              <textarea name="rawText" rows="10" [(ngModel)]="rawText"></textarea>
            </label>
            <button class="btn-primary" type="submit">Ingest</button>
            <p class="muted">{{ message }}</p>
          </form>
        </section>

        <section class="panel">
          <h2>Documents</h2>
          <div class="list-row" *ngFor="let document of documents">
            <div>
              <strong>{{ document.title }}</strong>
              <p>{{ document.kind }} · {{ document.status }} · {{ document.status_message }}</p>
            </div>
          </div>
        </section>
      </div>

      <section class="panel">
        <div class="panel-head">
          <h2>Profile Facts</h2>
          <input class="compact-input" placeholder="Search facts" [(ngModel)]="factSearch" (keyup.enter)="loadFacts()">
        </div>
        <div class="fact-grid">
          <article class="fact-card" *ngFor="let fact of facts">
            <div class="card-line">
              <span class="status-chip">{{ fact.fact_type }}</span>
              <span class="status-chip" [class.good]="fact.verified_by_user">{{ fact.verified_by_user ? 'verified' : fact.confidence }}</span>
            </div>
            <h3>{{ fact.title }}</h3>
            <p>{{ fact.statement }}</p>
            <small>{{ fact.source_document_title }}</small>
            <button class="btn-mini" type="button" *ngIf="!fact.verified_by_user" (click)="verify(fact)">Verify</button>
          </article>
        </div>
      </section>
    </section>
  `,
})
export class ProfileComponent implements OnInit {
  documents: ProfileDocument[] = [];
  facts: ProfileFact[] = [];
  kind = 'resume';
  title = 'Canonical Resume';
  rawText = '';
  factSearch = '';
  message = '';
  private file?: File;

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.documents().subscribe((page) => this.documents = page.results);
    this.loadFacts();
  }

  loadFacts(): void {
    const params: Record<string, string> = this.factSearch ? { search: this.factSearch } : {};
    this.api.facts(params).subscribe((page) => this.facts = page.results);
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.file = input.files?.[0];
    if (this.file && !this.title) {
      this.title = this.file.name;
    }
  }

  createDocument(): void {
    const payload = new FormData();
    payload.set('kind', this.kind);
    payload.set('title', this.title || 'Profile source');
    payload.set('raw_text', this.rawText);
    if (this.file) {
      payload.set('upload', this.file);
    }
    this.message = 'Queued for ingestion.';
    this.api.createDocument(payload).subscribe({
      next: () => {
        this.rawText = '';
        this.file = undefined;
        this.load();
      },
      error: () => this.message = 'Could not ingest document.',
    });
  }

  verify(fact: ProfileFact): void {
    this.api.verifyFact(fact.id).subscribe((updated) => {
      fact.verified_by_user = updated.verified_by_user;
    });
  }
}
