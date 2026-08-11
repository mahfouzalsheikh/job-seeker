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
          <p class="page-intro">Keep polished resumes and future application assets organized.</p>
        </div>
        <a class="btn-primary" routerLink="/resume-lab">Open Resume Lab</a>
      </div>

      <section class="panel empty-state artifact-empty">
        <span class="empty-icon">□</span><p class="eyebrow">Artifact library</p><h2>Your finished materials will live here</h2>
        <p>Export reviewed resume drafts from Resume Lab. Support for cover letters, recruiter messages, and interview prep is ready to grow with your workflow.</p>
        <a class="btn-primary" routerLink="/resume-lab">Create a resume →</a>
      </section>
    </section>
  `,
})
export class ArtifactsComponent {}
