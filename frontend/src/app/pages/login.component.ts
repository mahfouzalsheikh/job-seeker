import { CommonModule } from '@angular/common';
import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

@Component({
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <main class="auth-page">
      <section class="auth-panel">
        <h1>Job Search Studio</h1>
        <p>Sign in with your Django user account.</p>
        <form (ngSubmit)="login()">
          <label>
            Username
            <input name="username" [(ngModel)]="username" autocomplete="username">
          </label>
          <label>
            Password
            <input name="password" type="password" [(ngModel)]="password" autocomplete="current-password">
          </label>
          <button class="btn-primary" type="submit" [disabled]="loading">Login</button>
          <p class="error" *ngIf="error">{{ error }}</p>
        </form>
      </section>
    </main>
  `,
})
export class LoginComponent {
  username = 'admin';
  password = 'adminpass';
  loading = false;
  error = '';

  constructor(private auth: AuthService, private router: Router) {}

  login(): void {
    this.loading = true;
    this.error = '';
    this.auth.login(this.username, this.password).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigate(['/dashboard']);
      },
      error: () => {
        this.loading = false;
        this.error = 'Login failed. Check the username and password.';
      },
    });
  }
}

