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
      <aside class="side-nav">
        <div class="side-nav-head">
          <a class="brand" routerLink="/dashboard">Job Search Studio</a>
          <span class="socket-status" [class.connected]="socketStatus === 'connected'" [title]="socketStatus">
            <span></span>
          </span>
        </div>

        <nav class="side-nav-main" aria-label="Primary">
          <a routerLink="/dashboard" [class.active]="active('/dashboard')">Dashboard</a>
          <a routerLink="/profile" [class.active]="active('/profile')">Profile</a>
          <a routerLink="/matches" [class.active]="active('/matches')">Matches</a>
          <a routerLink="/resume-lab" [class.active]="active('/resume-lab')">Resume Lab</a>
          <a routerLink="/pipeline" [class.active]="active('/pipeline')">Pipeline</a>
          <a routerLink="/sources" [class.active]="active('/sources')">Sources</a>
          <a routerLink="/strategy" [class.active]="active('/strategy')">Strategy</a>
          <a routerLink="/artifacts" [class.active]="active('/artifacts')">Artifacts</a>
          <a routerLink="/settings" [class.active]="active('/settings')">Settings</a>
        </nav>

        <div class="side-nav-context">
          <span class="side-nav-context-label">Latest event</span>
          <p>{{ latestEvent }}</p>
        </div>

        <button class="btn-mini side-nav-logout" type="button" (click)="logout()">Logout</button>
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
  private navSub?: Subscription;
  private statusSub?: Subscription;
  private eventsSub?: Subscription;

  constructor(
    public auth: AuthService,
    private router: Router,
    private realtime: RealtimeService,
  ) {}

  ngOnInit(): void {
    this.currentPath = this.router.url;
    if (this.auth.hasSession()) {
      this.realtime.connect();
    }
    this.navSub = this.router.events.pipe(filter((event) => event instanceof NavigationEnd)).subscribe((event) => {
      const nav = event as NavigationEnd;
      this.currentPath = nav.urlAfterRedirects || nav.url;
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
    this.statusSub?.unsubscribe();
    this.eventsSub?.unsubscribe();
  }

  active(path: string): boolean {
    return this.currentPath === path || this.currentPath.startsWith(`${path}/`);
  }

  logout(): void {
    this.auth.logout();
    this.realtime.disconnect();
    this.router.navigate(['/login']);
  }
}

