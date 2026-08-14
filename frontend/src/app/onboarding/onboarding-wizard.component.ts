import { CommonModule } from '@angular/common';
import { Component, EventEmitter, OnDestroy, OnInit, Output } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, OnboardingQuestion, OnboardingSnapshot } from '../services/api.service';

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
          <p>I read the evidence first, then choose the next question from what is missing or unclear—not from a fixed script.</p>
          <div class="agent-progress" *ngIf="snapshot"><div><span>Profile confidence</span><strong>{{ snapshot.assessment.confidence }}%</strong></div><i><b [style.width.%]="snapshot.progress"></b></i></div>
          <div class="agent-memory" *ngIf="snapshot"><span><b>{{ snapshot.stats.facts }}</b> facts</span><span><b>{{ snapshot.stats.skills }}</b> skills</span><span><b>{{ snapshot.stats.achievements }}</b> wins</span></div>
          <div class="resume-memory" *ngIf="snapshot?.resume?.analysis?.overview"><small>CURRENT RESUME</small><p>{{ snapshot?.resume?.analysis?.overview }}</p></div>
          <div class="agent-trust"><span>✓</span><p><strong>You approve the truth.</strong> Ambiguous claims always come back to you.</p></div>
        </aside>

        <main class="onboarding-conversation">
          <header>
            <div><span class="mobile-agent">P</span><div><small>PROFILE STEWARD</small><strong>{{ working ? workingLabel : 'Adaptive interview ready' }}</strong></div></div>
            <button type="button" class="onboarding-close" (click)="close()" aria-label="Finish onboarding later">×</button>
          </header>

          <div class="onboarding-loading" *ngIf="loading"><span class="thinking-dots"><i></i><i></i><i></i></span><p>Reviewing your evidence and choosing the next useful question…</p></div>

          <div class="question-stage" *ngIf="snapshot && !loading">
            <div class="agent-question">
              <span class="question-avatar">P</span>
              <div><small>Profile Steward <ng-container *ngIf="step === 'interview'">· Question {{ snapshot.interview.turn }}</ng-container></small><h1 id="onboarding-title">{{ snapshot.step.title }}</h1><p>{{ snapshot.step.prompt }}</p></div>
            </div>
            <p class="wizard-error" role="alert" *ngIf="error">{{ error }}</p>

            <section class="answer-card welcome-answer" *ngIf="step === 'welcome'">
              <div class="outcome-list">
                <div><span>01</span><p><strong>Upload your current resume</strong><small>PDF, Word, HTML, ODT, RTF, Markdown, or text</small></p></div>
                <div><span>02</span><p><strong>Let the agent find the gaps</strong><small>Questions change with your chronology, evidence, and ambiguity</small></p></div>
                <div><span>03</span><p><strong>Confirm what matters</strong><small>You resolve uncertainty before the profile becomes actionable</small></p></div>
              </div>
              <button class="btn-primary wizard-primary" type="button" (click)="answer('welcome', {})" [disabled]="working">Start with my resume →</button>
              <small class="time-note">One focused question at a time · progress is saved</small>
            </section>

            <section class="answer-card" *ngIf="step === 'source'">
              <label class="onboarding-file" [class.has-file]="sourceFile" (dragover)="allowDrop($event)" (drop)="onDrop($event)">
                <input type="file" accept=".pdf,.doc,.docx,.html,.htm,.odt,.rtf,.txt,.md" (change)="onSourceFile($event)">
                <span class="upload-icon">⇧</span><strong>{{ sourceFile?.name || 'Upload your current resume' }}</strong>
                <small>PDF, Word, HTML, ODT, RTF, TXT, or Markdown · up to 15 MB</small>
                <em>{{ sourceFile ? readableSize(sourceFile.size) + ' · Choose a different file' : 'Choose file or drop it here' }}</em>
              </label>
              <div class="source-error" *ngIf="snapshot.resume?.status === 'failed'"><strong>I could not finish that resume.</strong><span>{{ snapshot.resume?.message }}</span></div>
              <div class="or-line"><span>or paste the current resume</span></div>
              <textarea rows="5" [(ngModel)]="sourceText" placeholder="Paste the full resume text here…"></textarea>
              <button class="btn-primary wizard-primary" type="button" (click)="uploadSource()" [disabled]="working || (!sourceFile && !sourceText.trim())"><span class="spinner" *ngIf="working"></span>{{ working ? 'Uploading your resume…' : 'Analyze my resume →' }}</button>
              <small class="privacy-note">Your resume becomes private profile evidence. Forth does not make unclear claims true.</small>
            </section>

            <section class="answer-card processing-answer" *ngIf="step === 'source_processing'">
              <div class="document-reading"><span>CV</span><div><i></i><i></i><i></i><i></i></div></div>
              <h3>Reading evidence, not just keywords</h3>
              <p>I’m mapping roles, dates, education, capabilities, projects, scope, and measurable impact—then separating clear facts from details that need you.</p>
              <div class="analysis-steps"><span class="done">✓ Text extracted</span><span class="active"><i class="spinner"></i> Career evidence analysis</span><span>○ Dynamic question planning</span></div>
            </section>

            <section class="answer-card dynamic-answer" *ngIf="step === 'interview' && question" [attr.data-question-target]="question.target" [attr.data-question-id]="question.id">
              <div class="resume-evidence" *ngIf="question.evidence"><small>WHAT YOUR RESUME SAYS</small><blockquote>{{ question.evidence }}</blockquote></div>
              <div class="answer-proposal" *ngIf="question.suggestions.length">
                <div><span>✦</span><p><strong>Profile Steward's draft</strong>{{ question.suggestion_reason }}</p></div>
                <div class="proposal-list"><button type="button" *ngFor="let suggestion of question.suggestions" (click)="applySuggestion(suggestion)">{{ suggestion }}<small>Use or edit</small></button></div>
              </div>

              <label *ngIf="question.kind === 'text' || question.kind === 'tags' || question.kind === 'number'">
                Your answer <span *ngIf="question.kind === 'tags'">Comma separated</span>
                <input [type]="question.kind === 'number' ? 'number' : 'text'" [(ngModel)]="answerText" [placeholder]="question.placeholder" (keydown.enter)="submitOnEnter($event)">
              </label>
              <label *ngIf="question.kind === 'textarea' || question.kind === 'confirm'">
                {{ question.kind === 'confirm' ? 'Confirm or correct this claim' : 'Your answer' }}
                <textarea [rows]="question.kind === 'confirm' ? 5 : 7" [(ngModel)]="answerText" [placeholder]="question.placeholder"></textarea>
              </label>
              <fieldset *ngIf="question.kind === 'single_choice' || question.kind === 'multi_choice'">
                <legend>Choose {{ question.kind === 'multi_choice' ? 'all that apply' : 'one option' }}</legend>
                <div class="choice-chips dynamic-choices"><button type="button" *ngFor="let option of question.options" [class.selected]="choiceValues.includes(option)" (click)="choose(option)"><span>{{ choiceValues.includes(option) ? '✓' : '+' }}</span>{{ option }}</button></div>
                <div class="custom-choice"><input [(ngModel)]="customChoiceText" placeholder="Add or edit your own answer"><button type="button" (click)="addCustomChoice()" [disabled]="!customChoiceText.trim()">Add</button></div>
              </fieldset>

              <div class="question-why"><span>✦</span><p><strong>Why I’m asking</strong>{{ question.why }}</p></div>
              <div class="wizard-actions dynamic-actions">
                <button class="btn-primary" type="button" (click)="submitInterview()" [disabled]="working || !hasDynamicAnswer"><span class="spinner" *ngIf="working"></span>{{ working ? 'Updating your profile…' : question.kind === 'confirm' ? 'Confirm & continue →' : 'Save & continue →' }}</button>
                <button class="text-button" type="button" *ngIf="!question.required" (click)="submitInterview(true)" [disabled]="working">Skip for now</button>
              </div>
            </section>

            <section class="answer-card review-answer" *ngIf="step === 'review'">
              <div class="readiness-ring" [style.--score]="snapshot.readiness.score"><strong>{{ snapshot.readiness.score }}%</strong><span>ready</span></div>
              <div class="review-copy"><h3>Ready for sourcing and matching</h3><p>{{ snapshot.profile.headline }}</p><div class="review-targets"><span *ngFor="let role of snapshot.profile.target_roles">{{ role }}</span></div></div>
              <div class="readiness-checks"><div *ngFor="let check of checkEntries(snapshot.readiness.checks)" [class.passed]="check[1]"><span>{{ check[1] ? '✓' : '·' }}</span>{{ check[0] }}</div></div>
              <div class="profile-signal"><div><strong>{{ snapshot.stats.facts }}</strong><span>career facts</span></div><div><strong>{{ snapshot.stats.skills }}</strong><span>capabilities</span></div><div><strong>{{ snapshot.stats.achievements }}</strong><span>proof points</span></div><div><strong>{{ snapshot.stats.preferences }}</strong><span>preferences</span></div></div>
              <div class="ambiguity-clear"><span>✓</span><p><strong>No unresolved resume ambiguity</strong><small>The profile is grounded in your resume and confirmed answers.</small></p></div>
              <button class="btn-primary wizard-primary" type="button" (click)="complete()" [disabled]="working || !snapshot.readiness.ready"><span class="spinner" *ngIf="working"></span>{{ snapshot.needs_onboarding ? 'Activate my job search →' : 'Return to Forth →' }}</button>
              <button class="text-button" type="button" (click)="close()">Review the full profile first</button>
            </section>
          </div>

          <footer *ngIf="snapshot && step !== 'welcome'"><span><b class="agent-live"></b>{{ step === 'interview' ? 'Next question is replanned after every answer' : 'Profile analysis is resumable' }}</span><button type="button" (click)="close()">Finish later</button></footer>
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
  workingLabel = 'Working on your profile…';
  error = '';
  sourceFile?: File;
  sourceText = '';
  answerText = '';
  choiceValues: string[] = [];
  customChoiceText = '';
  private pollTimer?: number;
  private lastQuestionId = '';

  constructor(private api: ApiService) {}
  ngOnInit(): void { this.load(); }
  ngOnDestroy(): void { if (this.pollTimer) window.clearTimeout(this.pollTimer); }
  get step(): string { return this.snapshot?.step.id || ''; }
  get question(): OnboardingQuestion | undefined { return this.snapshot?.step.question || undefined; }
  get hasDynamicAnswer(): boolean {
    if (!this.question) return false;
    if (this.question.kind === 'single_choice' || this.question.kind === 'multi_choice') return this.choiceValues.length > 0;
    return Boolean(this.answerText.trim());
  }

  load(): void {
    this.api.onboarding().subscribe({
      next: (snapshot) => {
        this.snapshot = snapshot; this.loading = false; this.working = false; this.hydrateQuestion(snapshot);
        if (snapshot.step.id === 'source_processing') this.schedulePoll();
      },
      error: () => { this.error = 'Could not load onboarding. You can finish this from Candidate Profile.'; this.loading = false; this.working = false; },
    });
  }

  answer(step: string, answers: Record<string, any>): void {
    this.working = true; this.workingLabel = 'Replanning the interview…'; this.error = '';
    this.api.answerOnboarding(step, answers).subscribe({
      next: (snapshot) => { this.snapshot = snapshot; this.working = false; this.hydrateQuestion(snapshot); if (snapshot.step.id === 'source_processing') this.schedulePoll(); },
      error: (error) => { this.working = false; this.error = error?.error?.detail || 'I could not save that answer. Please check it and try again.'; },
    });
  }

  close(): void { sessionStorage.setItem('forth_onboarding_dismissed', '1'); this.closed.emit(); }
  complete(): void {
    if (!this.snapshot?.needs_onboarding) { this.close(); return; }
    this.working = true; this.workingLabel = 'Activating your profile…';
    this.api.answerOnboarding('complete', {}).subscribe({ next: () => this.close(), error: (error) => { this.working = false; this.error = error?.error?.detail || 'A required profile signal is still missing.'; } });
  }
  allowDrop(event: DragEvent): void { event.preventDefault(); }
  onDrop(event: DragEvent): void { event.preventDefault(); const file = event.dataTransfer?.files?.[0]; if (file) this.setSourceFile(file); }
  onSourceFile(event: Event): void { const file = (event.target as HTMLInputElement).files?.[0]; if (file) this.setSourceFile(file); }
  setSourceFile(file: File): void {
    const allowed = ['pdf', 'doc', 'docx', 'html', 'htm', 'odt', 'rtf', 'txt', 'md'];
    const extension = file.name.split('.').pop()?.toLowerCase() || '';
    if (!allowed.includes(extension)) { this.error = 'Use a PDF, Word, HTML, ODT, RTF, text, or Markdown resume.'; this.sourceFile = undefined; return; }
    if (file.size > 15 * 1024 * 1024) { this.error = 'Choose a resume that is 15 MB or smaller.'; this.sourceFile = undefined; return; }
    this.error = ''; this.sourceFile = file;
  }
  readableSize(size: number): string { return size < 1024 * 1024 ? `${Math.max(1, Math.round(size / 1024))} KB` : `${(size / 1024 / 1024).toFixed(1)} MB`; }
  uploadSource(): void {
    if (!this.sourceFile && !this.sourceText.trim()) return;
    const form = new FormData(); form.set('kind', 'resume'); form.set('title', this.sourceFile?.name || 'Pasted current resume'); form.set('raw_text', this.sourceText); if (this.sourceFile) form.set('upload', this.sourceFile);
    this.working = true; this.workingLabel = 'Uploading your resume…'; this.error = '';
    this.api.createDocument(form).subscribe({ next: () => this.load(), error: (response) => { this.working = false; this.error = response?.error?.upload?.[0] || 'I could not read that resume. Try another file or paste its text instead.'; } });
  }

  choose(option: string): void {
    if (!this.question) return;
    if (this.question.kind === 'single_choice') { this.choiceValues = [option]; return; }
    const index = this.choiceValues.indexOf(option); index >= 0 ? this.choiceValues.splice(index, 1) : this.choiceValues.push(option);
  }
  applySuggestion(suggestion: string): void {
    if (!this.question) return;
    if (this.question.kind === 'single_choice' || this.question.kind === 'multi_choice') {
      if (!this.choiceValues.includes(suggestion)) this.choose(suggestion);
      return;
    }
    if (this.question.kind === 'tags') {
      this.answerText = Array.from(new Set([...this.values(this.answerText), ...this.values(suggestion)])).join(', ');
      return;
    }
    this.answerText = suggestion;
  }
  addCustomChoice(): void {
    const value = this.customChoiceText.trim();
    if (!value || !this.question) return;
    if (this.question.kind === 'single_choice') this.choiceValues = [value];
    else if (!this.choiceValues.includes(value)) this.choiceValues.push(value);
    this.customChoiceText = '';
  }
  submitOnEnter(event: Event): void { event.preventDefault(); if (this.hasDynamicAnswer && !this.working) this.submitInterview(); }
  submitInterview(skip = false): void {
    if (!this.question) return;
    const choiceQuestion = this.question.kind === 'single_choice' || this.question.kind === 'multi_choice';
    let value: string | string[] = choiceQuestion ? this.choiceValues : this.answerText;
    if (this.question.kind === 'tags') value = this.values(this.answerText);
    this.answer('interview', { question_id: this.question.id, value, skip });
  }
  values(value: string): string[] { return String(value || '').split(',').map((item) => item.trim()).filter(Boolean); }
  checkEntries(checks: Record<string, boolean>): [string, boolean][] { return Object.entries(checks); }

  private hydrateQuestion(snapshot: OnboardingSnapshot): void {
    const question = snapshot.step.question;
    if (!question || question.id === this.lastQuestionId) return;
    this.lastQuestionId = question.id;
    this.answerText = question.prefill || '';
    this.choiceValues = question.prefill ? this.values(question.prefill) : [];
    this.customChoiceText = '';
  }
  private schedulePoll(): void { if (this.pollTimer) window.clearTimeout(this.pollTimer); this.pollTimer = window.setTimeout(() => this.load(), 1500); }
}
