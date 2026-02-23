import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import {
  LoginRequest, RegisterRequest, TokenResponse, UserInfo, UserResponse
} from '../models/auth.models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'surogate_token';

  token = signal<string | null>(localStorage.getItem(this.TOKEN_KEY));

  currentUser = computed<UserInfo | null>(() => {
    const t = this.token();
    if (!t) return null;
    try {
      const payload = JSON.parse(atob(t.split('.')[1]));
      return { username: payload.sub, role: payload.role, exp: payload.exp };
    } catch {
      return null;
    }
  });

  isAuthenticated = computed<boolean>(() => {
    const u = this.currentUser();
    if (!u) return false;
    return u.exp * 1000 > Date.now();
  });

  constructor(private http: HttpClient, private config: ApiConfigService) {}

  login(req: LoginRequest): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.config.apiUrl}/auth/login`, req).pipe(
      tap(resp => this.storeToken(resp.access_token))
    );
  }

  register(req: RegisterRequest): Observable<UserResponse> {
    return this.http.post<UserResponse>(`${this.config.apiUrl}/auth/register`, req);
  }

  logout(): void {
    this.token.set(null);
    localStorage.removeItem(this.TOKEN_KEY);
  }

  private storeToken(t: string): void {
    this.token.set(t);
    localStorage.setItem(this.TOKEN_KEY, t);
  }
}
