import { CommonModule } from '@angular/common';
import { Component, OnDestroy, OnInit } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter, Subscription } from 'rxjs';
import { AuthService } from './services/auth.service';
import { RealtimeService, RealtimeStatus } from './services/realtime.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, RouterLink],
  template: `
    <div class="app-shell" *ngIf="auth.hasSession(); else authOnly">
      <header class="mobile-header">
        <a class="mobile-brand" routerLink="/dashboard" (click)="closeNav()">
          <span class="brand-mark">JS</span>
          <span>Job Search Studio</span>
        </a>
        <button class="menu-toggle" type="button" (click)="navOpen = !navOpen" [attr.aria-expanded]="navOpen" aria-label="Toggle navigation">
          <span></span><span></span><span></span>
        </button>
      </header>

      <button class="nav-backdrop" type="button" *ngIf="navOpen" (click)="closeNav()" aria-label="Close navigation"></button>

      <aside class="side-nav" [class.open]="navOpen">
        <div class="side-nav-head">
          <a class="brand" routerLink="/dashboard" (click)="closeNav()">
            <span class="brand-mark">JS</span>
            <span class="brand-copy"><strong>Job Search</strong><small>Studio</small></span>
          </a>
          <button class="nav-close" type="button" (click)="closeNav()" aria-label="Close navigation">×</button>
        </div>

        <nav class="side-nav-main" aria-label="Primary">
          <span class="nav-section-label">Your search</span>
          <a routerLink="/dashboard" [class.active]="active('/dashboard')" [attr.aria-current]="active('/dashboard') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">⌂</span>Today</a>
          <a routerLink="/concierge" [class.active]="active('/concierge')" [attr.aria-current]="active('/concierge') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">✦</span>Concierge</a>
          <a routerLink="/matches" [class.active]="active('/matches')" [attr.aria-current]="active('/matches') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">◇</span>Opportunities</a>
          <a routerLink="/pipeline" [class.active]="active('/pipeline')" [attr.aria-current]="active('/pipeline') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">▦</span>Applications</a>
          <a routerLink="/resume-lab" [class.active]="active('/resume-lab')" [attr.aria-current]="active('/resume-lab') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">▤</span>Document Studio</a>

          <span class="nav-section-label nav-section-spaced">Knowledge & tools</span>
          <a routerLink="/profile" [class.active]="active('/profile')" [attr.aria-current]="active('/profile') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">◎</span>Candidate Profile</a>
          <a routerLink="/sources" [class.active]="active('/sources')" [attr.aria-current]="active('/sources') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">⌁</span>Sources</a>
          <a routerLink="/strategy" [class.active]="active('/strategy')" [attr.aria-current]="active('/strategy') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">↗</span>Strategy</a>
          <a routerLink="/artifacts" [class.active]="active('/artifacts')" [attr.aria-current]="active('/artifacts') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">□</span>Artifacts</a>
          <a routerLink="/settings" [class.active]="active('/settings')" [attr.aria-current]="active('/settings') ? 'page' : null" (click)="closeNav()"><span class="nav-icon">⚙</span>Settings</a>
        </nav>

        <div class="side-nav-context">
          <div class="connection-row">
            <span class="socket-status" [class.connected]="socketStatus === 'connected'" [title]="socketStatus"><span></span></span>
            <div><strong>{{ socketStatus === 'connected' ? 'Live updates on' : socketStatus === 'connecting' ? 'Connecting' : 'Live updates off' }}</strong><small>{{ latestEvent }}</small></div>
          </div>
        </div>

        <button class="btn-secondary side-nav-logout" type="button" (click)="logout()"><span>↪</span> Sign out</button>
      </aside>

      <main class="app-main">
        <router-outlet></router-outlet>
      </main>
    </div>

    <ng-template #authOnly>
      <router-outlet></router-outlet>
    </ng-template>
  `,
})
export class AppComponent implements OnInit, OnDestroy {
  currentPath = '/dashboard';
  socketStatus: RealtimeStatus = 'disconnected';
  latestEvent = 'No events yet';
  navOpen = false;
  private navSub?: Subscription;
  private authSub?: Subscription;
  private statusSub?: Subscription;
  private eventsSub?: Subscription;

  constructor(
    public auth: AuthService,
    private router: Router,
    private realtime: RealtimeService,
  ) {}

  ngOnInit(): void {
    this.currentPath = this.router.url;
    this.authSub = this.auth.authed$.subscribe((authenticated) => {
      if (authenticated) {
        this.realtime.reconnect();
      } else {
        this.realtime.disconnect();
      }
    });
    this.navSub = this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe((event) => {
      const nav = event as NavigationEnd;
      this.currentPath = nav.urlAfterRedirects || nav.url;
      this.closeNav();
      if (this.auth.hasSession()) {
        this.realtime.connect();
      }
    });
    this.statusSub = this.realtime.status$.subscribe((status) => {
      this.socketStatus = status;
    });
    this.eventsSub = this.realtime.events$.subscribe((event) => {
      this.latestEvent = String(event.type || 'event').replaceAll('_', ' ');
    });
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
    this.authSub?.unsubscribe();
    this.statusSub?.unsubscribe();
    this.eventsSub?.unsubscribe();
  }

  active(path: string): boolean {
    return this.currentPath === path || this.currentPath.startsWith(`${path}/`);
  }

  closeNav(): void {
    this.navOpen = false;
  }

  logout(): void {
    this.auth.logout();
    this.realtime.disconnect();
    this.router.navigate(['/login']);
  }
}
