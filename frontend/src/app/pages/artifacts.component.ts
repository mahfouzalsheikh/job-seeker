import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Outputs</p>
          <h1>Artifacts</h1>
        </div>
        <a class="btn-primary" routerLink="/resume-lab">Open Resume Lab</a>
      </div>

      <section class="panel">
        <h2>Artifact Library</h2>
        <p>
          The MVP stores resume markdown exports through Resume Lab. The backend artifact model and API are ready
          for PDF, DOCX, cover letter, recruiter message, and interview-prep files.
        </p>
      </section>
    </section>
  `,
})
export class ArtifactsComponent {}

