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
          <p class="page-intro">Review your private workspace configuration and connected services.</p>
        </div>
      </div>

      <section class="panel">
        <div class="panel-head"><div><h2>Workspace runtime</h2><p>Core services powering Job Search Studio.</p></div><span class="status-chip good">● Runtime configured</span></div>
        <div class="settings-grid">
          <div><span>Backend</span><strong>Django / DRF</strong></div>
          <div><span>Async</span><strong>Celery / Redis</strong></div>
          <div><span>Realtime</span><strong>Django Channels</strong></div>
          <div><span>AI</span><strong>OpenAI API via backend</strong></div>
        </div>
        <div class="action-row"><a class="btn-primary" href="/job-search-studio-user-guide.html" target="_blank" rel="noopener">Open user guide ↗</a></div>
      </section>
    </section>
  `,
})
export class SettingsComponent {}
