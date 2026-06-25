import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export type RealtimeStatus = 'connected' | 'connecting' | 'disconnected';

@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private socket?: WebSocket;
  status$ = new BehaviorSubject<RealtimeStatus>('disconnected');
  events$ = new Subject<any>();

  constructor(private auth: AuthService) {}

  connect(): void {
    const token = this.auth.getAccessToken();
    if (!token || this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return;
    }
    this.status$.next('connecting');
    this.socket = new WebSocket(`${environment.wsBaseUrl}?token=${encodeURIComponent(token)}`);
    this.socket.onopen = () => this.status$.next('connected');
    this.socket.onmessage = (message) => {
      try {
        this.events$.next(JSON.parse(message.data));
      } catch {
        this.events$.next({ type: 'message', data: message.data });
      }
    };
    this.socket.onclose = () => this.status$.next('disconnected');
    this.socket.onerror = () => this.status$.next('disconnected');
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = undefined;
    this.status$.next('disconnected');
  }
}

