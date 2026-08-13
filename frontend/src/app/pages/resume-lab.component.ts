import { CommonModule } from '@angular/common';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, CoverLetter, JobPosting, Resume } from '../services/api.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page">
      <div class="page-head">
        <div>
          <p class="eyebrow">Application Materials</p>
          <h1>Resume Lab</h1>
          <p class="page-intro">Create evidence-backed resumes, review claim risks, and export polished drafts.</p>
        </div>
        <button class="btn-primary" type="button" (click)="activeTab = 'tailor'">✦ Tailor a resume</button>
      </div>

      <div class="tabs" role="tablist" aria-label="Resume Lab sections">
        <button type="button" role="tab" [class.active]="activeTab === 'library'" [attr.aria-selected]="activeTab === 'library'" (click)="activeTab = 'library'">Resume library <span>{{ resumes.length }}</span></button>
        <button type="button" role="tab" [class.active]="activeTab === 'create'" [attr.aria-selected]="activeTab === 'create'" (click)="activeTab = 'create'">Canonical resume</button>
        <button type="button" role="tab" [class.active]="activeTab === 'tailor'" [attr.aria-selected]="activeTab === 'tailor'" (click)="activeTab = 'tailor'">Tailored draft</button>
      </div>
      <p class="feedback-banner" *ngIf="message">{{ message }}</p>

      <section class="panel focused-form" *ngIf="activeTab === 'create'">
        <div class="panel-head"><div><h2>Create a canonical resume</h2><p>This becomes the trusted base for future tailored versions.</p></div></div>
        <label>Resume title<input [(ngModel)]="newTitle" name="newTitle" placeholder="Canonical Resume"></label>
        <label>Resume content <span class="field-hint">Markdown supported</span><textarea rows="18" [(ngModel)]="newMarkdown" name="newMarkdown" placeholder="Paste or write your master resume…"></textarea></label>
        <div class="action-row form-actions"><button class="btn-primary" type="button" (click)="createCanonical()" [disabled]="!newMarkdown.trim()">Save canonical resume</button><button class="btn-secondary" type="button" (click)="activeTab = 'library'">Cancel</button></div>
      </section>

      <section class="panel focused-form" *ngIf="activeTab === 'tailor'">
        <div class="generation-hero"><span class="generation-icon">✦</span><div><h2>Generate a tailored draft</h2><p>Select a target role. Forth uses your canonical resume and verified evidence to produce a focused version.</p></div></div>
        <label>Target opportunity<select [(ngModel)]="targetJobId" name="targetJobId"><option [ngValue]="null">Choose a job from your matches</option><option *ngFor="let job of jobs" [ngValue]="job.id">{{ job.title }} · {{ job.company }}</option></select></label>
        <div class="action-row form-actions"><button class="btn-primary" type="button" (click)="tailor()" [disabled]="!targetJobId || generating">{{ generating ? 'Generating…' : 'Generate tailored draft' }}</button><button class="btn-secondary" type="button" (click)="activeTab = 'library'" [disabled]="generating">Cancel</button></div>
      </section>

      <div class="workspace-grid" *ngIf="activeTab === 'library'">
        <section class="panel">
          <div class="panel-head"><div><h2>Saved materials</h2><p>{{ resumes.length }} resumes · {{ coverLetters.length }} cover letters</p></div><button class="icon-button" type="button" (click)="load()" aria-label="Refresh materials">↻</button></div>
          <button
            class="job-row"
            type="button"
            *ngFor="let resume of resumes"
            [class.selected]="selected?.id === resume.id"
            (click)="selected = resume; selectedLetter = undefined">
            <span>
              <strong>{{ resume.title }}</strong>
              <small>{{ resume.kind }} · {{ resume.target_job_title || 'Master version' }}</small>
            </span>
            <span class="status-chip" [class.good]="resume.approved">{{ resume.approved ? 'approved' : 'draft' }}</span>
          </button>
          <div class="empty-state small" *ngIf="!resumes.length"><span class="empty-icon">▤</span><h3>No resumes yet</h3><p>Create a canonical resume to get started.</p><button class="btn-primary" type="button" (click)="activeTab = 'create'">Create resume</button></div>
          <div class="section-divider" *ngIf="coverLetters.length"><span>Cover letters</span></div>
          <button class="job-row" type="button" *ngFor="let letter of coverLetters" [class.selected]="selectedLetter?.id === letter.id" (click)="selectedLetter = letter; selected = undefined"><span><strong>{{ letter.title }}</strong><small>Version {{ letter.version }} · {{ letter.target_job_title }}</small></span><span class="status-chip" [class.good]="letter.approved">{{ letter.approved ? 'approved' : 'draft' }}</span></button>
        </section>

        <section class="panel detail-panel" *ngIf="selected">
          <div class="panel-head">
            <div>
              <h2>{{ selected.title }}</h2>
              <p>{{ selected.kind }} · {{ selected.target_job_title || 'Canonical' }}</p>
            </div>
            <span class="status-chip" [class.good]="selected.approved">{{ selected.approved ? 'Approved' : 'Draft' }}</span>
          </div>

          <div class="validation-grid">
            <div>
              <span>Covered keywords</span>
              <strong>{{ (selected.validation?.keyword_coverage || []).length }}</strong>
            </div>
            <div>
              <span>Unsupported claims</span>
              <strong>{{ (selected.validation?.unsupported_claims || []).length }}</strong>
            </div>
            <div>
              <span>Weak claims</span>
              <strong>{{ (selected.validation?.weak_claims || []).length }}</strong>
            </div>
          </div>

          <h3>Review notes</h3>
          <div class="chip-row">
            <span class="status-chip warn" *ngFor="let note of selected.validation?.risk_notes || []">{{ note }}</span>
            <span class="muted" *ngIf="!(selected.validation?.risk_notes || []).length">No risk notes detected.</span>
          </div>

          <h3>Resume Markdown</h3>
          <pre class="resume-preview">{{ selected.content_markdown }}</pre>

          <label class="risk-accept" *ngIf="!selected.approved && (selected.validation?.unsupported_claims || []).length"><input type="checkbox" [(ngModel)]="acceptResumeRisk" name="acceptResumeRisk"><span>I reviewed the unsupported claims above and accept the risk for this version.</span></label>
          <div class="action-row">
            <button class="btn-primary" type="button" (click)="approve(selected)" *ngIf="!selected.approved" [disabled]="approvingResumeId === selected.id || ((selected.validation?.unsupported_claims || []).length && !acceptResumeRisk)"><span class="spinner" *ngIf="approvingResumeId === selected.id" aria-hidden="true"></span>{{ approvingResumeId === selected.id ? 'Approving…' : '✓ Approve draft' }}</button>
            <button class="btn-secondary" type="button" (click)="download(selected)">↓ Export markdown</button>
          </div>
        </section>

        <section class="panel detail-panel" *ngIf="selectedLetter">
          <div class="panel-head"><div><h2>{{ selectedLetter.title }}</h2><p>Cover letter · version {{ selectedLetter.version }}</p></div><span class="status-chip" [class.good]="selectedLetter.approved">{{ selectedLetter.approved ? 'Approved' : 'Draft' }}</span></div>
          <div class="validation-grid"><div><span>Evidence facts</span><strong>{{ (selectedLetter.content_json?.evidence_fact_ids || []).length }}</strong></div><div><span>Unsupported claims</span><strong>{{ (selectedLetter.validation?.unsupported_claims || []).length }}</strong></div><div><span>Risk notes</span><strong>{{ (selectedLetter.validation?.risk_notes || []).length }}</strong></div></div>
          <h3>Review notes</h3><div class="chip-row"><span class="status-chip warn" *ngFor="let note of selectedLetter.validation?.risk_notes || []">{{ note }}</span><span class="muted" *ngIf="!(selectedLetter.validation?.risk_notes || []).length">No risk notes detected.</span></div>
          <h3>Cover letter</h3><pre class="resume-preview">{{ selectedLetter.content_markdown }}</pre>
          <label class="risk-accept" *ngIf="!selectedLetter.approved && (selectedLetter.validation?.unsupported_claims || []).length"><input type="checkbox" [(ngModel)]="acceptLetterRisk" name="acceptLetterRisk"><span>I reviewed the unsupported claims above and accept the risk for this version.</span></label>
          <div class="action-row"><button class="btn-primary" type="button" (click)="approveLetter(selectedLetter)" *ngIf="!selectedLetter.approved" [disabled]="approvingLetterId === selectedLetter.id || ((selectedLetter.validation?.unsupported_claims || []).length && !acceptLetterRisk)"><span class="spinner" *ngIf="approvingLetterId === selectedLetter.id" aria-hidden="true"></span>{{ approvingLetterId === selectedLetter.id ? 'Approving…' : '✓ Approve cover letter' }}</button></div>
        </section>
      </div>
    </section>
  `,
})
export class ResumeLabComponent implements OnInit {
  resumes: Resume[] = [];
  coverLetters: CoverLetter[] = [];
  jobs: JobPosting[] = [];
  selected?: Resume;
  selectedLetter?: CoverLetter;
  targetJobId: number | null = null;
  newTitle = 'Canonical Resume';
  newMarkdown = '';
  message = '';
  generating = false;
  approvingResumeId: number | null = null;
  approvingLetterId: number | null = null;
  acceptResumeRisk = false;
  acceptLetterRisk = false;
  activeTab: 'library' | 'create' | 'tailor' = 'library';

  constructor(private api: ApiService) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.api.resumes().subscribe((page) => {
      this.resumes = page.results;
      if (!this.selected && this.resumes.length) {
        this.selected = this.resumes[0];
      }
    });
    this.api.jobs().subscribe((page) => this.jobs = page.results);
    this.api.coverLetters().subscribe((page) => this.coverLetters = page.results);
  }

  createCanonical(): void {
    this.api.createResume({
      kind: 'canonical',
      title: this.newTitle,
      content_markdown: this.newMarkdown,
      content_json: {},
    }).subscribe((resume) => {
      this.message = 'Canonical resume saved.';
      this.selected = resume;
      this.activeTab = 'library';
      this.load();
    });
  }

  tailor(): void {
    if (!this.targetJobId) return;
    this.message = 'Generating tailored resume.';
    this.generating = true;
    this.api.tailorResume(this.targetJobId).subscribe({
      next: (resume) => {
        this.message = 'Tailored resume created.';
        this.selected = resume;
        this.activeTab = 'library';
        this.generating = false;
        this.load();
      },
      error: () => {
        this.message = 'The tailored resume could not be generated. Please try again.';
        this.generating = false;
      },
    });
  }

  approve(resume: Resume): void {
    this.approvingResumeId = resume.id;
    this.api.approveResume(resume.id, this.acceptResumeRisk).subscribe((updated) => {
      this.selected = updated;
      this.approvingResumeId = null;
      this.acceptResumeRisk = false;
      this.load();
    }, (error) => { this.approvingResumeId = null; this.message = error?.error?.detail || 'Could not approve this resume.'; });
  }

  approveLetter(letter: CoverLetter): void {
    this.approvingLetterId = letter.id;
    this.api.approveCoverLetter(letter.id, this.acceptLetterRisk).subscribe((updated) => { this.selectedLetter = updated; this.approvingLetterId = null; this.acceptLetterRisk = false; this.load(); }, (error) => { this.approvingLetterId = null; this.message = error?.error?.detail || 'Could not approve this cover letter.'; });
  }

  download(resume: Resume): void {
    this.api.exportResumeMarkdown(resume.id).subscribe((blob) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${resume.title.toLowerCase().replaceAll(' ', '-')}.md`;
      anchor.click();
      URL.revokeObjectURL(url);
    });
  }
}
