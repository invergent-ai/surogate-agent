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

  readonly model              = signal<string>('');
  readonly apiKey             = signal<string>('');
  readonly openrouterProvider = signal<string>('');
  readonly vllmUrl            = signal<string>('');
  readonly vllmToolCalling    = signal<boolean>(true);
  readonly vllmTemperature    = signal<number | null>(null);
  readonly vllmTopK           = signal<number | null>(null);
  readonly vllmTopP           = signal<number | null>(null);
  readonly vllmMinP           = signal<number | null>(null);
  readonly vllmPresencePenalty = signal<number | null>(null);
  readonly vllmContextLength   = signal<number | null>(null);
  readonly thinkingEnabled        = signal<boolean>(false);
  readonly thinkingBudget         = signal<number>(10000);
  readonly expertLookupEnabled    = signal<boolean>(false);

  isConfigured(): boolean {
    const hasVllm = !!this.vllmUrl().trim();
    return !!this.model().trim() && (hasVllm || !!this.apiKey().trim());
  }

  /** Load model + api_key + openrouter_provider from the server profile. Call after login or on page init. */
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
          this.openrouterProvider.set(user.openrouter_provider ?? '');
          this.vllmUrl.set(user.vllm_url ?? '');
          this.vllmToolCalling.set(user.vllm_tool_calling ?? true);
          this.vllmTemperature.set(user.vllm_temperature ?? null);
          this.vllmTopK.set(user.vllm_top_k ?? null);
          this.vllmTopP.set(user.vllm_top_p ?? null);
          this.vllmMinP.set(user.vllm_min_p ?? null);
          this.vllmPresencePenalty.set(user.vllm_presence_penalty ?? null);
          this.vllmContextLength.set(user.vllm_context_length ?? null);
          this.thinkingEnabled.set(user.thinking_enabled ?? false);
          this.thinkingBudget.set(user.thinking_budget ?? 10000);
          this.expertLookupEnabled.set(user.expert_lookup_enabled ?? false);
        }),
        map(() => void 0),
        catchError(() => of(void 0)),
      );
  }

  /** Return all registered users with their LLM settings (developer-only). */
  getUsers(): Observable<UserResponse[]> {
    const token = this.auth.token();
    if (!token) return of([]);
    return this.http
      .get<UserResponse[]>(`${this.config.apiUrl}/auth/users`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      .pipe(catchError(() => of([])));
  }

  /** Persist all LLM settings to the server and update local signals. */
  saveSettings(
    model: string,
    apiKey: string,
    openrouterProvider: string = '',
    vllmUrl: string = '',
    vllmToolCalling: boolean = true,
    vllmTemperature: number | null = null,
    vllmTopK: number | null = null,
    vllmTopP: number | null = null,
    vllmMinP: number | null = null,
    vllmPresencePenalty: number | null = null,
    vllmContextLength: number | null = null,
    thinkingEnabled: boolean = false,
    thinkingBudget: number = 10000,
    expertLookupEnabled: boolean = false,
  ): Observable<void> {
    const token = this.auth.token();
    return this.http
      .put<UserResponse>(
        `${this.config.apiUrl}/auth/me`,
        {
          model, api_key: apiKey, openrouter_provider: openrouterProvider, vllm_url: vllmUrl,
          vllm_tool_calling: vllmToolCalling,
          vllm_temperature: vllmTemperature,
          vllm_top_k: vllmTopK,
          vllm_top_p: vllmTopP,
          vllm_min_p: vllmMinP,
          vllm_presence_penalty: vllmPresencePenalty,
          vllm_context_length: vllmContextLength,
          thinking_enabled: thinkingEnabled,
          thinking_budget: thinkingBudget,
          expert_lookup_enabled: expertLookupEnabled,
        },
        { headers: { Authorization: `Bearer ${token ?? ''}` } },
      )
      .pipe(
        tap(user => {
          this.model.set(user.model ?? model);
          this.apiKey.set(user.api_key ?? apiKey);
          this.openrouterProvider.set(user.openrouter_provider ?? openrouterProvider);
          this.vllmUrl.set(user.vllm_url ?? vllmUrl);
          this.vllmToolCalling.set(user.vllm_tool_calling ?? vllmToolCalling);
          this.vllmTemperature.set(user.vllm_temperature ?? vllmTemperature);
          this.vllmTopK.set(user.vllm_top_k ?? vllmTopK);
          this.vllmTopP.set(user.vllm_top_p ?? vllmTopP);
          this.vllmMinP.set(user.vllm_min_p ?? vllmMinP);
          this.vllmPresencePenalty.set(user.vllm_presence_penalty ?? vllmPresencePenalty);
          this.vllmContextLength.set(user.vllm_context_length ?? vllmContextLength);
          this.thinkingEnabled.set(user.thinking_enabled ?? thinkingEnabled);
          this.thinkingBudget.set(user.thinking_budget ?? thinkingBudget);
          this.expertLookupEnabled.set(user.expert_lookup_enabled ?? expertLookupEnabled);
        }),
        map(() => void 0),
      );
  }
}
