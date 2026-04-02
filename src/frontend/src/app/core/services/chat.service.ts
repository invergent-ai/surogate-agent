import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { ApiConfigService } from './api-config.service';
import { AuthService } from './auth.service';
import { SettingsService } from './settings.service';
import { ChatRequest, SseEvent } from '../models/chat.models';

@Injectable({ providedIn: 'root' })
export class ChatService {
  private config = inject(ApiConfigService);
  private auth   = inject(AuthService);
  private settings = inject(SettingsService);

  streamChat(req: ChatRequest): Observable<SseEvent> {
    return new Observable(subscriber => {
      const controller = new AbortController();

      (async () => {
        try {
          const token = this.auth.token();
          const headers: Record<string, string> = { 'Content-Type': 'application/json' };
          if (token) headers['Authorization'] = `Bearer ${token}`;

          // Merge model, api_key, and vLLM settings from saved settings.
          // Caller-supplied values (e.g. chatOverrides from user-test-panel) take precedence.
          const payload: ChatRequest = {
            ...req,
            model:               req.model               || this.settings.model(),
            api_key:             req.api_key             || this.settings.apiKey(),
            openrouter_provider: req.openrouter_provider || this.settings.openrouterProvider(),
            vllm_url:            req.vllm_url            || this.settings.vllmUrl(),
            vllm_tool_calling:     req.vllm_tool_calling     ?? this.settings.vllmToolCalling(),
            vllm_temperature:      req.vllm_temperature      ?? this.settings.vllmTemperature(),
            vllm_top_k:            req.vllm_top_k            ?? this.settings.vllmTopK(),
            vllm_top_p:            req.vllm_top_p            ?? this.settings.vllmTopP(),
            vllm_min_p:            req.vllm_min_p            ?? this.settings.vllmMinP(),
            vllm_presence_penalty: req.vllm_presence_penalty ?? this.settings.vllmPresencePenalty(),
            vllm_context_length:   req.vllm_context_length   ?? this.settings.vllmContextLength(),
            thinking_enabled:      req.thinking_enabled      ?? this.settings.thinkingEnabled(),
            thinking_budget:       req.thinking_budget       ?? this.settings.thinkingBudget(),
          };

          const resp = await fetch(`${this.config.apiUrl}/chat`, {
            method: 'POST',
            headers,
            body: JSON.stringify(payload),
            signal: controller.signal,
          });

          if (!resp.ok) {
            const err = await resp.json().catch(() => ({ detail: resp.statusText }));
            subscriber.error(err);
            return;
          }

          const reader = resp.body!.getReader();
          const decoder = new TextDecoder();
          let buffer = '';
          let eventName = '';
          let dataLine = '';

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            const lines = buffer.split('\n');
            buffer = lines.pop() ?? '';

            for (const rawLine of lines) {
              const line = rawLine.replace(/\r$/, ''); // normalize CRLF → LF
              if (line.startsWith('event:')) {
                eventName = line.slice(6).trim();
              } else if (line.startsWith('data:')) {
                dataLine = line.slice(5).trim();
              } else if (line === '' && eventName) {
                try {
                  const parsed = JSON.parse(dataLine);
                  subscriber.next({ event: eventName, data: parsed } as SseEvent);
                } catch {
                  // skip malformed lines
                }
                eventName = '';
                dataLine = '';
              }
            }
          }
          subscriber.complete();
        } catch (err: unknown) {
          if (err instanceof Error && err.name !== 'AbortError') {
            subscriber.error(err);
          } else {
            subscriber.complete();
          }
        }
      })();

      return () => controller.abort();
    });
  }
}
