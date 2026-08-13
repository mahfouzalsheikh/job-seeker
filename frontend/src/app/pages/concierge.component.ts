import { CommonModule } from '@angular/common';
import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';
import { ApiService, ApprovalRequest, ConversationThread } from '../services/api.service';
import { RealtimeService } from '../services/realtime.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <section class="page concierge-page">
      <div class="page-head concierge-head">
        <div>
          <p class="eyebrow">Forth concierge</p>
          <h1>Your job search has a chief of staff.</h1>
          <p class="page-intro">Ask for clarity, delegate research, and approve consequential work in one place.</p>
        </div>
        <span class="agent-online"><i></i> Six specialists ready</span>
      </div>

      <div class="concierge-layout">
        <section class="conversation-panel">
          <div class="conversation-toolbar">
            <div><strong>Forth Concierge</strong><small>Answers use your profile, matches, and pipeline</small></div>
            <button type="button" class="new-chat" (click)="newConversation()" [disabled]="sending || startingConversation">{{ startingConversation ? 'Starting…' : '+ New conversation' }}</button>
          </div>
          <div class="conversation-stream" #stream aria-live="polite">
            <div class="concierge-welcome" *ngIf="!thread?.messages?.length">
              <span class="concierge-orb">F</span>
              <h2>What would move your search forward today?</h2>
              <p>I can review your profile, refresh sources, explain matches, prepare materials, or surface the next pipeline action.</p>
              <div class="prompt-grid">
                <button type="button" *ngFor="let prompt of prompts" (click)="send(prompt)" [disabled]="sending">{{ prompt }} <span>↗</span></button>
              </div>
            </div>

            <article class="chat-message" *ngFor="let message of thread?.messages" [class.user-message]="message.role === 'user'">
              <span class="chat-avatar">{{ message.role === 'user' ? 'You' : 'F' }}</span>
              <div class="message-bubble">
                <small>{{ message.role === 'user' ? 'You' : agentName(message.metadata?.agent) }} <span>· {{ message.created_at | date:'shortTime' }}</span></small>
                <p class="message-copy">{{ message.content }}</p>
                <div class="message-actions" *ngIf="message.role === 'assistant' && message.metadata?.actions?.length">
                  <ng-container *ngFor="let action of message.metadata.actions">
                    <a *ngIf="action.kind === 'link'" [routerLink]="action.route">{{ action.label }} <span>→</span></a>
                    <button *ngIf="action.kind === 'prompt'" type="button" (click)="send(action.prompt, action.job_id)" [disabled]="sending">{{ action.label }} <span>→</span></button>
                  </ng-container>
                </div>
              </div>
            </article>
            <article class="chat-message thinking" *ngIf="sending" role="status"><span class="chat-avatar">F</span><div class="message-bubble"><small>{{ workingAgent }} is working</small><p><i></i><i></i><i></i><span>Reviewing your workspace…</span></p></div></article>
          </div>

          <form class="composer" (ngSubmit)="send(draft)">
            <div class="composer-error" *ngIf="chatError" role="alert">{{ chatError }}</div>
            <textarea [(ngModel)]="draft" name="draft" rows="2" aria-label="Message Forth Concierge" placeholder="Ask about your profile, opportunities, applications, or materials…" [disabled]="startingConversation" (keydown.control.enter)="$event.preventDefault(); send(draft)"></textarea>
            <div><span>Ctrl + Enter to send</span><button class="btn-primary" type="submit" [disabled]="!draft.trim() || sending || startingConversation">{{ sending ? 'Working…' : 'Send →' }}</button></div>
          </form>
        </section>

        <aside class="decision-rail">
          <div class="rail-head"><div><p class="eyebrow">Human control</p><h2>Decisions waiting</h2></div><span>{{ approvals.length }}</span></div>
          <article class="approval-card" *ngFor="let approval of approvals">
            <span class="status-chip warn">Approval required</span>
            <h3>{{ approval.title }}</h3>
            <p>{{ approval.prompt }}</p>
            <div class="approval-actions"><button class="btn-primary" type="button" (click)="decide(approval, true)" [disabled]="decidingApprovalId === approval.id"><span class="spinner" *ngIf="decidingApprovalId === approval.id" aria-hidden="true"></span>{{ decidingApprovalId === approval.id ? approvalProgress(approval) : 'Approve' }}</button><button class="btn-secondary" type="button" (click)="decide(approval, false)" [disabled]="decidingApprovalId === approval.id">Not now</button></div>
          </article>
          <div class="quiet-state" *ngIf="!approvals.length"><span>✓</span><strong>You’re in control</strong><p>No decisions are waiting. Agents can research and analyze without interrupting you.</p></div>

          <div class="agent-roster">
            <p class="eyebrow">Specialists</p>
            <div *ngFor="let agent of agents"><span [style.background]="agent.color">{{ agent.initial }}</span><p><strong>{{ agent.name }}</strong><small>{{ agent.role }}</small></p></div>
          </div>
        </aside>
      </div>
    </section>
  `,
})
export class ConciergeComponent implements OnInit, OnDestroy {
  @ViewChild('stream') private stream?: ElementRef<HTMLElement>;
  thread?: ConversationThread;
  approvals: ApprovalRequest[] = [];
  draft = '';
  sending = false;
  startingConversation = false;
  workingAgent = 'Forth Concierge';
  chatError = '';
  decidingApprovalId: number | null = null;
  private eventSub?: Subscription;
  private pollTimer?: ReturnType<typeof setTimeout>;
  private pendingRunId?: number;
  prompts = [
    'What should I focus on today?',
    'Find and rank new roles',
    'Where is my profile weakest?',
    'Prepare my strongest opportunity',
  ];
  agents = [
    { initial: 'P', name: 'Profile Steward', role: 'Evidence & context', color: '#c9f45a' },
    { initial: 'S', name: 'Sourcing Scout', role: 'Fresh opportunities', color: '#78e5dc' },
    { initial: 'M', name: 'Match Analyst', role: 'Fit & gaps', color: '#a991ff' },
    { initial: 'A', name: 'Application Coach', role: 'Pipeline & follow-ups', color: '#f0bd45' },
    { initial: 'D', name: 'Document Tailor', role: 'Application materials', color: '#ff8a70' },
    { initial: 'F', name: 'Forth Concierge', role: 'Intent & decisions', color: '#fffdf8' },
  ];

  constructor(private api: ApiService, private realtime: RealtimeService) {}

  ngOnInit(): void {
    this.load();
    this.eventSub = this.realtime.events$.subscribe((event) => {
      const type = String(event.type || '');
      if (type.startsWith('agent_') && this.pendingRunId) this.pollForResponse(this.pendingRunId, 0);
      if (type.startsWith('approval_')) this.loadApprovals();
    });
  }

  ngOnDestroy(): void {
    this.eventSub?.unsubscribe();
    if (this.pollTimer) clearTimeout(this.pollTimer);
  }

  load(): void {
    this.api.conversations().subscribe((page) => {
      if (page.results.length) {
        this.thread = page.results[0];
        this.scrollToLatest();
      } else {
        this.api.createConversation().subscribe((thread) => { this.thread = thread; this.scrollToLatest(); });
      }
    });
    this.loadApprovals();
  }

  send(content: string, jobId?: number): void {
    const value = content.trim();
    if (!value || !this.thread || this.sending || this.startingConversation) return;
    this.sending = true;
    this.chatError = '';
    this.workingAgent = 'Forth Concierge';
    this.draft = '';
    this.scrollToLatest();
    this.api.sendMessage(this.thread.id, value, jobId ? { job_id: jobId } : {}).subscribe({
      next: (run) => {
        this.pendingRunId = run.id;
        this.workingAgent = this.agentName(run.agent);
        this.pollForResponse(run.id, 0);
      },
      error: () => {
        this.sending = false;
        this.chatError = 'That message could not be sent. Your draft is safe to try again.';
        this.draft = value;
      },
    });
  }

  newConversation(): void {
    if (this.sending || this.startingConversation) return;
    this.startingConversation = true;
    this.chatError = '';
    this.api.createConversation().subscribe({
      next: (thread) => {
        this.thread = thread;
        this.startingConversation = false;
        this.scrollToLatest();
      },
      error: () => {
        this.startingConversation = false;
        this.chatError = 'A new conversation could not be started. Please try again.';
      },
    });
  }

  private pollForResponse(runId: number, attempt: number): void {
    if (!this.thread || this.pendingRunId !== runId) return;
    if (this.pollTimer) clearTimeout(this.pollTimer);
    this.api.conversation(this.thread.id).subscribe({
      next: (thread) => {
        if (this.pendingRunId !== runId) return;
        this.thread = thread;
        this.scrollToLatest();
        const completed = thread.messages.some((message) => message.role === 'assistant' && message.metadata?.run_id === runId);
        if (completed) {
          this.pendingRunId = undefined;
          this.sending = false;
          this.loadApprovals();
          return;
        }
        if (attempt >= 80) {
          this.pendingRunId = undefined;
          this.sending = false;
          this.chatError = 'This is taking longer than expected. You can keep this page open or try again.';
          return;
        }
        this.pollTimer = setTimeout(() => this.pollForResponse(runId, attempt + 1), attempt < 5 ? 600 : 1200);
      },
      error: () => {
        if (attempt >= 80) {
          this.pendingRunId = undefined;
          this.sending = false;
          this.chatError = 'I lost the connection while waiting for the response. Please try again.';
          return;
        }
        this.pollTimer = setTimeout(() => this.pollForResponse(runId, attempt + 1), 1200);
      },
    });
  }

  private loadApprovals(): void {
    this.api.approvals('pending').subscribe((page) => this.approvals = page.results);
  }

  private scrollToLatest(): void {
    setTimeout(() => {
      const element = this.stream?.nativeElement;
      if (element) element.scrollTop = element.scrollHeight;
    });
  }

  decide(approval: ApprovalRequest, approved: boolean): void {
    if (this.decidingApprovalId) return;
    this.decidingApprovalId = approval.id;
    this.api.decideApproval(approval.id, approved).subscribe({
      next: () => { this.decidingApprovalId = null; this.loadApprovals(); },
      error: () => { this.decidingApprovalId = null; },
    });
  }

  approvalProgress(approval: ApprovalRequest): string {
    if (approval.kind === 'render_bundle') return 'Rendering PDFs…';
    if (approval.kind === 'prepare_application') return 'Preparing materials…';
    return 'Saving decision…';
  }

  agentName(agent?: string): string {
    const names: Record<string, string> = { profile: 'Profile Steward', sourcing: 'Sourcing Scout', matching: 'Match Analyst', application: 'Application Coach', documents: 'Document Tailor', concierge: 'Forth Concierge' };
    return names[agent || ''] || 'Forth Concierge';
  }
}
