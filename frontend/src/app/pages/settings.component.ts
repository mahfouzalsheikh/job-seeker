import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';

@Component({
  standalone: true,
  imports: [CommonModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">System</p>
          <h1>Settings</h1>
        </div>
      </div>

      <section class="panel">
        <h2>Runtime</h2>
        <div class="settings-grid">
          <div><span>Backend</span><strong>Django / DRF</strong></div>
          <div><span>Async</span><strong>Celery / Redis</strong></div>
          <div><span>Realtime</span><strong>Django Channels</strong></div>
          <div><span>AI</span><strong>OpenAI API via backend</strong></div>
        </div>
      </section>
    </section>
  `,
})
export class SettingsComponent {}

