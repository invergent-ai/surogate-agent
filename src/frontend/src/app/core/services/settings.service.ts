import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { AuthService } from './auth.service';
import { UserResponse } from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private http   = inject(HttpClient);
  private config = inject(ApiConfigService);
  private auth   = inject(AuthService);

  readonly model  = signal<string>('');
  readonly apiKey = signal<string>('');

  isConfigured(): boolean {
    return !!this.model().trim() && !!this.apiKey().trim();
  }

  /** Load model + api_key from the server profile. Call after login or on page init. */
  loadSettings(): Observable<void> {
    const token = this.auth.token();
    if (!token) return of(void 0);
    return this.http
      .get<UserResponse>(`${this.config.apiUrl}/auth/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .pipe(
        tap(user => {
          this.model.set(user.model ?? '');
          this.apiKey.set(user.api_key ?? '');
        }),
        map(() => void 0),
        catchError(() => of(void 0)),
      );
  }

  /** Persist model + api_key to the server and update local signals. */
  saveSettings(model: string, apiKey: string): Observable<void> {
    const token = this.auth.token();
    return this.http
      .put<UserResponse>(`${this.config.apiUrl}/auth/me`, { model, api_key: apiKey }, {
        headers: { Authorization: `Bearer ${token ?? ''}` },
      })
      .pipe(
        tap(user => {
          this.model.set(user.model ?? model);
          this.apiKey.set(user.api_key ?? apiKey);
        }),
        map(() => void 0),
      );
  }
}
