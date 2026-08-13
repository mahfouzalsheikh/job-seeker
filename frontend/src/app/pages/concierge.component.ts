import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Subscription, timer } from 'rxjs';
import { ApiService, ApprovalRequest, ConversationThread } from '../services/api.service';
import { RealtimeService } from '../services/realtime.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <section class="page concierge-page">
      <div class="page-head concierge-head">
        <div>
          <p class="eyebrow">Search concierge</p>
          <h1>Your job search has a chief of staff.</h1>
          <p class="page-intro">Ask for clarity, delegate research, and approve consequential work in one place.</p>
        </div>
        <span class="agent-online"><i></i> Six specialists ready</span>
      </div>

      <div class="concierge-layout">
        <section class="conversation-panel">
          <div class="conversation-stream" #stream>
            <div class="concierge-welcome" *ngIf="!thread?.messages?.length">
              <span class="concierge-orb">JS</span>
              <h2>What would move your search forward today?</h2>
              <p>I can review your profile, refresh sources, explain matches, prepare materials, or surface the next pipeline action.</p>
              <div class="prompt-grid">
                <button type="button" *ngFor="let prompt of prompts" (click)="send(prompt)">{{ prompt }} <span>↗</span></button>
              </div>
            </div>

            <article class="chat-message" *ngFor="let message of thread?.messages" [class.user-message]="message.role === 'user'">
              <span class="chat-avatar">{{ message.role === 'user' ? 'You' : 'JS' }}</span>
              <div><small>{{ message.role === 'user' ? 'You' : agentName(message.metadata?.agent) }}</small><p>{{ message.content }}</p></div>
            </article>
            <article class="chat-message thinking" *ngIf="sending"><span class="chat-avatar">JS</span><div><small>Specialist working</small><p><i></i><i></i><i></i></p></div></article>
          </div>

          <form class="composer" (ngSubmit)="send(draft)">
            <textarea [(ngModel)]="draft" name="draft" rows="2" placeholder="Ask about your profile, opportunities, applications, or materials…" (keydown.control.enter)="send(draft)"></textarea>
            <div><span>Ctrl + Enter to send</span><button class="btn-primary" type="submit" [disabled]="!draft.trim() || sending">{{ sending ? 'Working…' : 'Send →' }}</button></div>
          </form>
        </section>

        <aside class="decision-rail">
          <div class="rail-head"><div><p class="eyebrow">Human control</p><h2>Decisions waiting</h2></div><span>{{ approvals.length }}</span></div>
          <article class="approval-card" *ngFor="let approval of approvals">
            <span class="status-chip warn">Approval required</span>
            <h3>{{ approval.title }}</h3>
            <p>{{ approval.prompt }}</p>
            <div class="approval-actions"><button class="btn-primary" type="button" (click)="decide(approval, true)">Approve</button><button class="btn-secondary" type="button" (click)="decide(approval, false)">Not now</button></div>
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
  thread?: ConversationThread;
  approvals: ApprovalRequest[] = [];
  draft = '';
  sending = false;
  private eventSub?: Subscription;
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
    { initial: 'C', name: 'Search Concierge', role: 'Intent & decisions', color: '#fffdf8' },
  ];

  constructor(private api: ApiService, private realtime: RealtimeService) {}

  ngOnInit(): void {
    this.load();
    this.eventSub = this.realtime.events$.subscribe((event) => {
      if (String(event.type || '').startsWith('agent_') || String(event.type || '').startsWith('approval_')) this.refreshSoon();
    });
  }

  ngOnDestroy(): void { this.eventSub?.unsubscribe(); }

  load(): void {
    this.api.conversations().subscribe((page) => {
      if (page.results.length) {
        this.thread = page.results[0];
      } else {
        this.api.createConversation().subscribe((thread) => this.thread = thread);
      }
    });
    this.api.approvals('pending').subscribe((page) => this.approvals = page.results);
  }

  send(content: string): void {
    const value = content.trim();
    if (!value || !this.thread || this.sending) return;
    this.sending = true;
    this.draft = '';
    this.api.sendMessage(this.thread.id, value).subscribe({
      next: () => this.refreshSoon(),
      error: () => this.sending = false,
    });
  }

  refreshSoon(): void {
    timer(900).subscribe(() => {
      if (this.thread) this.api.conversation(this.thread.id).subscribe((thread) => { this.thread = thread; this.sending = false; });
      this.api.approvals('pending').subscribe((page) => this.approvals = page.results);
    });
  }

  decide(approval: ApprovalRequest, approved: boolean): void {
    this.api.decideApproval(approval.id, approved).subscribe(() => this.load());
  }

  agentName(agent: string): string {
    const names: Record<string, string> = { profile: 'Profile Steward', sourcing: 'Sourcing Scout', matching: 'Match Analyst', application: 'Application Coach', documents: 'Document Tailor', concierge: 'Search Concierge' };
    return names[agent] || 'Search Concierge';
  }
}
