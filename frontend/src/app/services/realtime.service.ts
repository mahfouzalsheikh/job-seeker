import { Injectable } from '@angular/core';
import { BehaviorSubject, Subject } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './auth.service';

export type RealtimeStatus = 'connected' | 'connecting' | 'disconnected';

@Injectable({ providedIn: 'root' })
export class RealtimeService {
  private socket?: WebSocket;
  private reconnectTimer?: ReturnType<typeof setTimeout>;
  private shouldReconnect = false;
  status$ = new BehaviorSubject<RealtimeStatus>('disconnected');
  events$ = new Subject<any>();

  constructor(private auth: AuthService) {}

  connect(): void {
    const token = this.auth.getAccessToken();
    if (!token || this.socket?.readyState === WebSocket.OPEN || this.socket?.readyState === WebSocket.CONNECTING) {
      return;
    }
    this.shouldReconnect = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    this.status$.next('connecting');
    const socket = new WebSocket(`${environment.wsBaseUrl}?token=${encodeURIComponent(token)}`);
    this.socket = socket;
    socket.onopen = () => {
      if (this.socket === socket) this.status$.next('connected');
    };
    socket.onmessage = (message) => {
      if (this.socket !== socket) return;
      try {
        this.events$.next(JSON.parse(message.data));
      } catch {
        this.events$.next({ type: 'message', data: message.data });
      }
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.socket = undefined;
      this.status$.next('disconnected');
      this.scheduleReconnect();
    };
    socket.onerror = () => {
      if (this.socket === socket) this.status$.next('disconnected');
    };
  }

  reconnect(): void {
    this.shouldReconnect = true;
    const previous = this.socket;
    this.socket = undefined;
    previous?.close();
    this.connect();
  }

  disconnect(): void {
    this.shouldReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = undefined;
    }
    const previous = this.socket;
    this.socket = undefined;
    previous?.close();
    this.status$.next('disconnected');
  }

  private scheduleReconnect(): void {
    if (!this.shouldReconnect || this.reconnectTimer || !this.auth.hasSession()) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = undefined;
      this.connect();
    }, 2000);
  }
}
