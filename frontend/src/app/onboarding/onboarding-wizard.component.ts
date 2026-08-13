import { CommonModule } from '@angular/common';
import { Component, EventEmitter, OnDestroy, OnInit, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, OnboardingSnapshot } from '../services/api.service';

@Component({
  selector: 'app-onboarding-wizard',
  standalone: true,
  imports: [CommonModule, FormsModule],
  styleUrl: './onboarding-wizard.component.css',
  template: `
    <div class="onboarding-backdrop" role="presentation">
      <section class="onboarding-modal" role="dialog" aria-modal="true" aria-labelledby="onboarding-title">
        <aside class="onboarding-agent">
          <div class="onboarding-brand"><span>F</span><strong>Forth</strong></div>
          <div class="steward-orb">P</div>
          <p class="eyebrow">Profile Steward</p>
          <h2>Your career context, assembled with you.</h2>
          <p>I’ll ask only what the evidence cannot tell me, then hand a ready-to-use profile to the rest of your specialist team.</p>
          <div class="agent-progress" *ngIf="snapshot"><div><span>Profile readiness</span><strong>{{ snapshot.readiness.score }}%</strong></div><i><b [style.width.%]="snapshot.progress"></b></i></div>
          <div class="agent-memory" *ngIf="snapshot"><span><b>{{ snapshot.stats.facts }}</b> facts</span><span><b>{{ snapshot.stats.skills }}</b> skills</span><span><b>{{ snapshot.stats.achievements }}</b> wins</span></div>
          <div class="agent-trust"><span>✓</span><p><strong>You approve the truth.</strong> I never invent career facts.</p></div>
        </aside>

        <main class="onboarding-conversation">
          <header>
            <div><span class="mobile-agent">P</span><div><small>PROFILE STEWARD</small><strong>{{ working ? 'Working on your profile…' : 'Ready' }}</strong></div></div>
            <button type="button" class="onboarding-close" (click)="close()" aria-label="Finish onboarding later">×</button>
          </header>

          <div class="onboarding-loading" *ngIf="loading"><span class="thinking-dots"><i></i><i></i><i></i></span><p>Reading your workspace and choosing the next useful question…</p></div>

          <div class="question-stage" *ngIf="snapshot && !loading">
            <div class="agent-question">
              <span class="question-avatar">P</span>
              <div><small>Profile Steward</small><h1 id="onboarding-title">{{ snapshot.step.title }}</h1><p>{{ snapshot.step.prompt }}</p></div>
            </div>
            <p class="wizard-error" role="alert" *ngIf="error">{{ error }}</p>

            <section class="answer-card welcome-answer" *ngIf="step === 'welcome'">
              <div class="outcome-list"><div><span>01</span><p><strong>Bring your evidence</strong><small>Resume, project notes, reviews, or your own answers</small></p></div><div><span>02</span><p><strong>Fill only the gaps</strong><small>Direction, constraints, strengths, impact, and preferences</small></p></div><div><span>03</span><p><strong>Review the signal</strong><small>A reusable profile for sourcing, matching, and documents</small></p></div></div>
              <button class="btn-primary wizard-primary" type="button" (click)="answer('welcome', {})">Build my candidate profile →</button>
              <small class="time-note">Usually 6–10 minutes · progress is saved</small>
            </section>

            <section class="answer-card" *ngIf="step === 'source'">
              <label class="onboarding-file" [class.has-file]="sourceFile"><input type="file" accept=".pdf,.docx,.txt,.md" (change)="onSourceFile($event)"><span class="upload-icon">⇧</span><strong>{{ sourceFile?.name || 'Drop in your current resume' }}</strong><small>PDF, DOCX, TXT, or Markdown · it does not need to be polished</small><em>{{ sourceFile ? 'Choose a different file' : 'Choose file' }}</em></label>
              <div class="or-line"><span>or paste what you have</span></div>
              <textarea rows="5" [(ngModel)]="sourceText" placeholder="Paste resume text, a LinkedIn summary, or career notes…"></textarea>
              <div class="wizard-actions"><button class="btn-primary" type="button" (click)="uploadSource()" [disabled]="working || (!sourceFile && !sourceText.trim())"><span class="spinner" *ngIf="working"></span>{{ working ? 'Uploading…' : 'Read my career history →' }}</button><button class="text-button" type="button" (click)="answer('source', { skip: true })" [disabled]="working">I’ll answer from scratch</button></div>
            </section>

            <section class="answer-card processing-answer" *ngIf="step === 'source_processing'">
              <div class="document-reading"><span>CV</span><div><i></i><i></i><i></i><i></i></div></div>
              <h3>Turning your document into reusable evidence</h3><p>Roles, skills, achievements, education, and dates are being separated into facts. I’ll ask about anything important that is still missing.</p>
              <div class="processing-status"><span class="spinner"></span> Extracting and organizing your profile…</div>
            </section>

            <section class="answer-card" *ngIf="step === 'direction'">
              <label>Your professional headline<input [(ngModel)]="headline" placeholder="e.g. Product-minded Staff Engineer building reliable AI platforms"></label>
              <label>Roles you want next <span>Comma separated</span><input [(ngModel)]="rolesText" placeholder="Staff Engineer, Engineering Lead"></label>
              <label>Industries or domains <span>Optional</span><input [(ngModel)]="industriesText" placeholder="Developer tools, AI infrastructure, fintech"></label>
              <button class="btn-primary wizard-primary" type="button" (click)="submitDirection()" [disabled]="working">Continue →</button>
            </section>

            <section class="answer-card" *ngIf="step === 'logistics'">
              <div class="answer-grid"><label>Current location<input [(ngModel)]="location" placeholder="Toronto, Canada"></label><label>Authorized to work in <span>Comma separated</span><input [(ngModel)]="countriesText" placeholder="Canada, United States"></label></div>
              <fieldset><legend>Preferred work modes</legend><div class="choice-chips"><button type="button" *ngFor="let option of workModeOptions" [class.selected]="workModes.includes(option.value)" (click)="toggle(workModes, option.value)"><span>{{ option.icon }}</span>{{ option.label }}</button></div></fieldset>
              <fieldset><legend>Employment types</legend><div class="choice-chips compact"><button type="button" *ngFor="let option of employmentOptions" [class.selected]="employmentTypes.includes(option)" (click)="toggle(employmentTypes, option)">{{ option }}</button></div></fieldset>
              <div class="answer-grid"><label>Minimum compensation <span>Optional</span><input type="number" [(ngModel)]="minimumCompensation" placeholder="150000"></label><label>Currency<select [(ngModel)]="currency"><option>CAD</option><option>USD</option><option>EUR</option><option>GBP</option></select></label></div>
              <button class="btn-primary wizard-primary" type="button" (click)="submitLogistics()" [disabled]="working">Save my boundaries →</button>
            </section>

            <section class="answer-card" *ngIf="step === 'strengths'">
              <label>Core skills and capabilities <span>Comma separated</span><input [(ngModel)]="skillsText" placeholder="Platform architecture, Python, technical leadership"></label>
              <label>What are you trusted to do especially well?<textarea rows="5" [(ngModel)]="capability" placeholder="Describe the kind of problems people bring to you and how you approach them…"></textarea></label>
              <div class="prompt-hint"><span>✦</span> Think beyond tools: leadership, judgment, communication, domain knowledge, and ways of working count.</div>
              <button class="btn-primary wizard-primary" type="button" (click)="submitStrengths()" [disabled]="working">Add these strengths →</button>
            </section>

            <section class="answer-card" *ngIf="step === 'impact'">
              <label>Name this accomplishment<input [(ngModel)]="impactTitle" placeholder="e.g. Cut deployment recovery time by 40%"></label>
              <label>What was the situation, what did you do, and what changed?<textarea rows="7" [(ngModel)]="impactStory" placeholder="Include scale, constraints, collaborators, and a measurable result when you can…"></textarea></label>
              <div class="prompt-hint"><span>✦</span> One concrete story gives matching and resume generation more signal than ten generic responsibilities.</div>
              <button class="btn-primary wizard-primary" type="button" (click)="submitImpact()" [disabled]="working">Save this proof point →</button>
            </section>

            <section class="answer-card" *ngIf="step === 'preferences'">
              <fieldset><legend>I do my best work when…</legend><div class="choice-chips text"><button type="button" *ngFor="let option of idealOptions" [class.selected]="idealPreferences.includes(option)" (click)="toggle(idealPreferences, option)">{{ option }}</button></div></fieldset>
              <label>Add another positive signal<input [(ngModel)]="customIdeal" placeholder="e.g. The team values written decision-making"></label>
              <fieldset><legend>I want to avoid…</legend><div class="choice-chips text avoid"><button type="button" *ngFor="let option of avoidOptions" [class.selected]="avoidPreferences.includes(option)" (click)="toggle(avoidPreferences, option)">{{ option }}</button></div></fieldset>
              <label>Add another boundary<input [(ngModel)]="customAvoid" placeholder="e.g. Roles with more than 25% travel"></label>
              <button class="btn-primary wizard-primary" type="button" (click)="submitPreferences()" [disabled]="working">Use these preferences →</button>
            </section>

            <section class="answer-card" *ngIf="step === 'summary'">
              <div class="draft-label"><span>✦</span><p><strong>I drafted this from what you told me.</strong><small>Make sure the emphasis sounds like you.</small></p></div>
              <label>Your professional through-line<textarea rows="9" [(ngModel)]="professionalSummary"></textarea></label>
              <button class="btn-primary wizard-primary" type="button" (click)="submitSummary()" [disabled]="working">This represents me →</button>
            </section>

            <section class="answer-card review-answer" *ngIf="step === 'review'">
              <div class="readiness-ring" [style.--score]="snapshot.readiness.score"><strong>{{ snapshot.readiness.score }}%</strong><span>ready</span></div>
              <div class="review-copy"><h3>Ready for sourcing and matching</h3><p>{{ snapshot.profile.headline }}</p><div class="review-targets"><span *ngFor="let role of snapshot.profile.target_roles">{{ role }}</span></div></div>
              <div class="readiness-checks"><div *ngFor="let check of checkEntries(snapshot.readiness.checks)" [class.passed]="check[1]"><span>{{ check[1] ? '✓' : '·' }}</span>{{ check[0] }}</div></div>
              <div class="profile-signal"><div><strong>{{ snapshot.stats.facts }}</strong><span>career facts</span></div><div><strong>{{ snapshot.stats.skills }}</strong><span>capabilities</span></div><div><strong>{{ snapshot.stats.achievements }}</strong><span>proof points</span></div><div><strong>{{ snapshot.stats.preferences }}</strong><span>preferences</span></div></div>
              <button class="btn-primary wizard-primary" type="button" (click)="complete()" [disabled]="working || !snapshot.readiness.ready"><span class="spinner" *ngIf="working"></span>{{ snapshot.needs_onboarding ? 'Activate my job search →' : 'Return to Forth →' }}</button>
              <button class="text-button" type="button" (click)="close()">Review the full profile first</button>
            </section>
          </div>

          <footer *ngIf="snapshot && step !== 'welcome'"><span>Step adapts as your profile grows</span><button type="button" (click)="close()">Finish later</button></footer>
        </main>
      </section>
    </div>
  `,
})
export class OnboardingWizardComponent implements OnInit, OnDestroy {
  @Output() closed = new EventEmitter<void>();
  snapshot?: OnboardingSnapshot;
  loading = true;
  working = false;
  error = '';
  sourceFile?: File;
  sourceText = '';
  headline = '';
  rolesText = '';
  industriesText = '';
  location = '';
  countriesText = '';
  workModes: string[] = [];
  employmentTypes: string[] = ['full-time'];
  minimumCompensation: number | null = null;
  currency = 'CAD';
  skillsText = '';
  capability = '';
  impactTitle = '';
  impactStory = '';
  idealPreferences: string[] = [];
  avoidPreferences: string[] = [];
  customIdeal = '';
  customAvoid = '';
  professionalSummary = '';
  workModeOptions = [{ value: 'remote', label: 'Remote', icon: '⌂' }, { value: 'hybrid', label: 'Hybrid', icon: '◫' }, { value: 'onsite', label: 'On-site', icon: '⌾' }];
  employmentOptions = ['full-time', 'contract', 'part-time'];
  idealOptions = ['High ownership', 'Strong mentorship', 'Deep technical work', 'Customer proximity', 'Clear mission', 'Calm collaboration'];
  avoidOptions = ['Always-on culture', 'Unclear ownership', 'Heavy travel', 'Pure people management'];
  private pollTimer?: number;
  private lastStep = '';

  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(); }
  ngOnDestroy(): void { if (this.pollTimer) window.clearTimeout(this.pollTimer); }
  get step(): string { return this.snapshot?.step.id || ''; }

  load(): void {
    this.api.onboarding().subscribe({ next: (snapshot) => { this.snapshot = snapshot; this.loading = false; this.working = false; this.hydrate(snapshot); if (snapshot.step.id === 'source_processing') this.schedulePoll(); }, error: () => { this.error = 'Could not load onboarding. You can finish this from Candidate Profile.'; this.loading = false; } });
  }

  answer(step: string, answers: Record<string, any>): void {
    this.working = true; this.error = '';
    this.api.answerOnboarding(step, answers).subscribe({ next: (snapshot) => { this.snapshot = snapshot; this.working = false; this.hydrate(snapshot); if (snapshot.step.id === 'source_processing') this.schedulePoll(); }, error: (error) => { this.working = false; this.error = error?.error?.detail || 'I could not save that answer. Please check it and try again.'; } });
  }

  close(): void { sessionStorage.setItem('forth_onboarding_dismissed', '1'); this.closed.emit(); }
  complete(): void { if (!this.snapshot?.needs_onboarding) { this.close(); return; } this.working = true; this.api.answerOnboarding('complete', {}).subscribe({ next: () => this.close(), error: (error) => { this.working = false; this.error = error?.error?.detail || 'A required profile signal is still missing.'; } }); }
  onSourceFile(event: Event): void { this.sourceFile = (event.target as HTMLInputElement).files?.[0]; }
  uploadSource(): void {
    if (!this.sourceFile && !this.sourceText.trim()) return;
    const form = new FormData(); form.set('kind', 'resume'); form.set('title', this.sourceFile?.name || 'Onboarding career history'); form.set('raw_text', this.sourceText); if (this.sourceFile) form.set('upload', this.sourceFile);
    this.working = true; this.error = '';
    this.api.createDocument(form).subscribe({ next: () => this.load(), error: () => { this.working = false; this.error = 'I could not read that source. Try another file or paste the text instead.'; } });
  }

  submitDirection(): void { this.answer('direction', { headline: this.headline, target_roles: this.values(this.rolesText), target_industries: this.values(this.industriesText) }); }
  submitLogistics(): void { this.answer('logistics', { location: this.location, authorized_countries: this.values(this.countriesText), work_modes: this.workModes, employment_types: this.employmentTypes, minimum_compensation: this.minimumCompensation, compensation_currency: this.currency }); }
  submitStrengths(): void { this.answer('strengths', { skills: this.values(this.skillsText), capability: this.capability }); }
  submitImpact(): void { this.answer('impact', { title: this.impactTitle, story: this.impactStory }); }
  submitPreferences(): void { this.answer('preferences', { ideal: [...this.idealPreferences, ...this.values(this.customIdeal)], avoid: [...this.avoidPreferences, ...this.values(this.customAvoid)] }); }
  submitSummary(): void { this.answer('summary', { professional_summary: this.professionalSummary }); }
  toggle(values: string[], value: string): void { const index = values.indexOf(value); index >= 0 ? values.splice(index, 1) : values.push(value); }
  values(value: string): string[] { return String(value || '').split(',').map((item) => item.trim()).filter(Boolean); }
  checkEntries(checks: Record<string, boolean>): [string, boolean][] { return Object.entries(checks); }

  private hydrate(snapshot: OnboardingSnapshot): void {
    if (this.lastStep === snapshot.step.id) return;
    this.lastStep = snapshot.step.id;
    const profile = snapshot.profile;
    if (snapshot.step.id === 'direction') { this.headline = profile.headline; this.rolesText = profile.target_roles.join(', '); this.industriesText = profile.target_industries.join(', '); }
    if (snapshot.step.id === 'logistics') { this.location = profile.location; this.countriesText = profile.authorized_countries.join(', '); this.workModes = [...profile.work_modes]; this.employmentTypes = profile.employment_types.length ? [...profile.employment_types] : ['full-time']; this.minimumCompensation = profile.minimum_compensation; this.currency = profile.compensation_currency || 'CAD'; }
    if (snapshot.step.id === 'summary') this.professionalSummary = profile.professional_summary || snapshot.suggested_summary;
  }
  private schedulePoll(): void { if (this.pollTimer) window.clearTimeout(this.pollTimer); this.pollTimer = window.setTimeout(() => this.load(), 1400); }
}
