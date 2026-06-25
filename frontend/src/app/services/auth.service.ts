import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../environments/environment';

interface TokenResponse {
  access: string;
  refresh: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly accessKey = 'job_search_studio_access';
  private readonly refreshKey = 'job_search_studio_refresh';
  private readonly authedSubject = new BehaviorSubject<boolean>(this.hasSession());
  authed$ = this.authedSubject.asObservable();

  constructor(private http: HttpClient) {}

  login(username: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${environment.apiBaseUrl}/auth/login/`, { username, password }).pipe(
      tap((tokens) => {
        localStorage.setItem(this.accessKey, tokens.access);
        localStorage.setItem(this.refreshKey, tokens.refresh);
        this.authedSubject.next(true);
      }),
    );
  }

  refresh(): Observable<{ access: string }> {
    return this.http.post<{ access: string }>(`${environment.apiBaseUrl}/auth/refresh/`, {
      refresh: this.getRefreshToken(),
    }).pipe(
      tap((tokens) => {
        localStorage.setItem(this.accessKey, tokens.access);
        this.authedSubject.next(true);
      }),
    );
  }

  logout(): void {
    localStorage.removeItem(this.accessKey);
    localStorage.removeItem(this.refreshKey);
    this.authedSubject.next(false);
  }

  hasSession(): boolean {
    return Boolean(this.getAccessToken() || this.getRefreshToken());
  }

  getAccessToken(): string {
    return localStorage.getItem(this.accessKey) || '';
  }

  getRefreshToken(): string {
    return localStorage.getItem(this.refreshKey) || '';
  }
}

