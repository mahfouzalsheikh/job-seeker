import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription } from 'rxjs';
import { ApiService, ProfileDocument, ProfileFact } from '../services/api.service';
import { RealtimeService } from '../services/realtime.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Knowledge Base</p>
          <h1>Profile</h1>
          <p class="page-intro">Build a trusted library of career evidence for matching and tailored resumes.</p>
        </div>
        <button class="btn-secondary" type="button" (click)="load()">↻ Refresh</button>
      </div>

      <div class="summary-strip">
        <div><span>Profile facts</span><strong>{{ facts.length }}</strong></div>
        <div><span>Verified</span><strong>{{ verifiedCount() }}</strong></div>
        <div><span>Source documents</span><strong>{{ documents.length }}</strong></div>
      </div>

      <div class="tabs" role="tablist" aria-label="Profile sections">
        <button type="button" role="tab" [class.active]="activeTab === 'facts'" [attr.aria-selected]="activeTab === 'facts'" (click)="activeTab = 'facts'">Profile facts <span>{{ facts.length }}</span></button>
        <button type="button" role="tab" [class.active]="activeTab === 'sources'" [attr.aria-selected]="activeTab === 'sources'" (click)="activeTab = 'sources'">Source material <span>{{ documents.length }}</span></button>
      </div>
      <p class="feedback-banner" *ngIf="message">{{ message }}</p>

      <section class="panel" *ngIf="activeTab === 'facts'">
        <div class="panel-head">
          <div>
            <h2>Career evidence</h2>
            <p>Review extracted details and verify anything you want the studio to prioritize.</p>
          </div>
          <div class="search-field"><span>⌕</span><input class="compact-input" aria-label="Search facts" placeholder="Search facts" [(ngModel)]="factSearch" (input)="loadFacts()"></div>
        </div>
        <div class="fact-grid">
          <article class="fact-card" *ngFor="let fact of facts">
            <ng-container *ngIf="editingFactId === fact.id; else factView">
              <label>
                Type
                <select [(ngModel)]="factDraft.fact_type" [name]="'factType' + fact.id">
                  <option *ngFor="let type of factTypes" [value]="type">{{ type }}</option>
                </select>
              </label>
              <label>
                Title
                <input [(ngModel)]="factDraft.title" [name]="'factTitle' + fact.id">
              </label>
              <label>
                Statement
                <textarea rows="5" [(ngModel)]="factDraft.statement" [name]="'factStatement' + fact.id"></textarea>
              </label>
              <label>
                Normalized value
                <input [(ngModel)]="factDraft.normalized_value" [name]="'factNormalized' + fact.id">
              </label>
              <div class="edit-grid compact-edit-grid">
                <label>
                  Confidence
                  <select [(ngModel)]="factDraft.confidence" [name]="'factConfidence' + fact.id">
                    <option *ngFor="let confidence of confidenceOptions" [value]="confidence">{{ confidence }}</option>
                  </select>
                </label>
                <label class="checkbox-label">
                  <input type="checkbox" [(ngModel)]="factDraft.verified_by_user" [name]="'factVerified' + fact.id">
                  Verified
                </label>
              </div>
              <div class="action-row">
                <button class="btn-primary" type="button" (click)="saveFact(fact)">Save</button>
                <button class="btn-secondary" type="button" (click)="cancelEdit()">Cancel</button>
              </div>
            </ng-container>

            <ng-template #factView>
              <div class="card-line">
                <span class="status-chip">{{ fact.fact_type }}</span>
                <span class="status-chip" [class.good]="fact.verified_by_user">{{ fact.verified_by_user ? 'verified' : fact.confidence }}</span>
              </div>
              <h3>{{ fact.title }}</h3>
              <p>{{ fact.statement }}</p>
              <small *ngIf="fact.source_document_title">From {{ fact.source_document_title }}</small>
              <div class="action-row">
                <button class="btn-mini" type="button" *ngIf="!fact.verified_by_user" (click)="verify(fact)">Verify</button>
                <button class="btn-mini" type="button" (click)="editFact(fact)">Edit</button>
                <button class="btn-mini btn-danger" type="button" (click)="deleteFact(fact)">Delete</button>
              </div>
            </ng-template>
          </article>
        </div>
        <div class="empty-state" *ngIf="!facts.length">
          <span class="empty-icon">◎</span>
          <h3>No profile facts yet</h3>
          <p>Add source material and the studio will extract reusable career evidence.</p>
          <button class="btn-primary" type="button" (click)="activeTab = 'sources'">Add source material</button>
        </div>
      </section>

      <div class="two-col profile-source-grid" *ngIf="activeTab === 'sources'">
        <section class="panel">
          <div class="panel-head compact-heading">
            <div><span class="section-icon">＋</span><h2>Add source material</h2></div>
          </div>
          <p class="section-copy">Upload a resume or paste notes, reviews, and project details.</p>
          <form class="stack" (ngSubmit)="createDocument()">
            <div class="edit-grid">
              <label>Type
                <select name="kind" [(ngModel)]="kind">
                  <option value="resume">Resume</option><option value="note">Note</option><option value="conversation">Conversation</option><option value="project">Project</option><option value="review">Review</option>
                </select>
              </label>
              <label>Title<input name="title" [(ngModel)]="title" placeholder="e.g. 2026 master resume"></label>
            </div>
            <label class="file-drop">Upload a file<input type="file" (change)="onFile($event)"><span>PDF, DOCX, or plain text</span></label>
            <label>Or paste text<textarea name="rawText" rows="9" [(ngModel)]="rawText" placeholder="Paste resume content, accomplishments, feedback, or project notes…"></textarea></label>
            <div class="action-row form-actions"><button class="btn-primary" type="submit">Extract profile facts</button></div>
          </form>
        </section>

        <section class="panel">
          <div class="panel-head"><div><h2>Source documents</h2><p>Your ingestion history and current processing status.</p></div></div>
          <div class="document-list">
            <div class="list-row" *ngFor="let document of documents">
              <span class="document-icon">{{ document.kind === 'resume' ? 'CV' : 'TXT' }}</span>
              <div class="list-row-main"><strong>{{ document.title }}</strong><p>{{ document.kind }} · {{ document.status_message }}</p></div>
              <span class="status-chip" [class.good]="document.status === 'ready'">{{ document.status }}</span>
            </div>
          </div>
          <div class="empty-state small" *ngIf="!documents.length"><span class="empty-icon">□</span><h3>No source documents</h3><p>Your uploaded material will appear here.</p></div>
        </section>
      </div>
    </section>
  `,
})
export class ProfileComponent implements OnInit, OnDestroy {
  documents: ProfileDocument[] = [];
  facts: ProfileFact[] = [];
  factTypes = ['skill', 'achievement', 'role', 'project', 'metric', 'preference', 'constraint', 'education'];
  confidenceOptions = ['low', 'medium', 'high'];
  kind = 'resume';
  title = 'Canonical Resume';
  rawText = '';
  factSearch = '';
  message = '';
  activeTab: 'facts' | 'sources' = 'facts';
  editingFactId: number | null = null;
  factDraft: Partial<ProfileFact> = {};
  private file?: File;
  private realtimeSub?: Subscription;

  constructor(private api: ApiService, private realtime: RealtimeService) {}

  ngOnInit(): void {
    this.load();
    this.realtimeSub = this.realtime.events$.subscribe((event) => {
      if (['profile_ingestion_finished', 'profile_fact_updated', 'profile_fact_deleted'].includes(event.type)) {
        this.load();
      }
    });
  }

  ngOnDestroy(): void {
    this.realtimeSub?.unsubscribe();
  }

  load(): void {
    this.api.documents().subscribe((page) => this.documents = page.results);
    this.loadFacts();
  }

  loadFacts(): void {
    const params: Record<string, string> = this.factSearch ? { search: this.factSearch } : {};
    this.api.facts(params).subscribe((page) => this.facts = page.results);
  }

  verifiedCount(): number {
    return this.facts.filter((fact) => fact.verified_by_user).length;
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

  editFact(fact: ProfileFact): void {
    this.editingFactId = fact.id;
    this.factDraft = { ...fact };
  }

  cancelEdit(): void {
    this.editingFactId = null;
    this.factDraft = {};
  }

  saveFact(fact: ProfileFact): void {
    const payload: Partial<ProfileFact> = {
      fact_type: String(this.factDraft.fact_type || fact.fact_type),
      title: String(this.factDraft.title || '').trim(),
      statement: String(this.factDraft.statement || '').trim(),
      normalized_value: String(this.factDraft.normalized_value || '').trim(),
      confidence: String(this.factDraft.confidence || fact.confidence),
      verified_by_user: Boolean(this.factDraft.verified_by_user),
    };
    if (!payload.title || !payload.statement) {
      this.message = 'Title and statement are required.';
      return;
    }
    this.api.updateFact(fact.id, payload).subscribe({
      next: (updated) => {
        Object.assign(fact, updated);
        this.message = 'Profile fact saved.';
        this.cancelEdit();
      },
      error: () => this.message = 'Could not save profile fact.',
    });
  }

  deleteFact(fact: ProfileFact): void {
    if (!confirm(`Delete "${fact.title}"?`)) {
      return;
    }
    this.api.deleteFact(fact.id).subscribe({
      next: () => {
        this.facts = this.facts.filter((item) => item.id !== fact.id);
        this.message = 'Profile fact deleted.';
        if (this.editingFactId === fact.id) {
          this.cancelEdit();
        }
      },
      error: () => this.message = 'Could not delete profile fact.',
    });
  }
}
