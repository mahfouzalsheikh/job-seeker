import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, Artifact } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page">
      <div class="page-head"><div><p class="eyebrow">Versioned outputs</p><h1>Artifact library</h1><p class="page-intro">The exact resumes, cover letters, previews, and PDFs associated with each application.</p></div><a class="btn-primary" routerLink="/resume-lab">Open Document Studio</a></div>
      <section class="artifact-grid" *ngIf="artifacts.length">
        <article class="artifact-card" *ngFor="let artifact of artifacts"><span class="artifact-kind">{{ artifact.kind.replaceAll('_', ' ') }}</span><div class="document-glyph"><i></i><i></i><i></i><i></i></div><h2>{{ artifact.title }}</h2><p>{{ artifact.mime_type || 'Stored content' }}</p><button class="btn-secondary" type="button" *ngIf="artifact.file_url" (click)="open(artifact)" [disabled]="openingId === artifact.id"><span class="spinner" *ngIf="openingId === artifact.id" aria-hidden="true"></span>{{ openingId === artifact.id ? 'Opening…' : 'Open artifact ↗' }}</button><span class="status-chip warn" *ngIf="artifact.metadata?.render_error">HTML fallback</span></article>
      </section>
      <section class="panel empty-state artifact-empty" *ngIf="!artifacts.length"><span class="empty-icon">□</span><p class="eyebrow">Artifact library</p><h2>Approved outputs will live here</h2><p>Prepare an application, review its claims, and approve PDF rendering from the application workspace.</p><a class="btn-primary" routerLink="/matches">Review opportunities →</a></section>
    </section>
  `,
})
export class ArtifactsComponent implements OnInit {
  artifacts: Artifact[] = [];
  openingId: number | null = null;
  message = '';
  constructor(private api: ApiService) {}
  ngOnInit(): void { this.api.artifacts().subscribe((page) => this.artifacts = page.results); }

  open(artifact: Artifact): void {
    this.openingId = artifact.id;
    this.api.downloadArtifact(artifact.id).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        window.open(url, '_blank', 'noopener');
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
        this.openingId = null;
      },
      error: () => { this.openingId = null; this.message = 'Could not open this artifact.'; },
    });
  }
}
