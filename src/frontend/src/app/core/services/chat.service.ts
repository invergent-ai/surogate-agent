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

          // Merge model and api_key from settings (caller values take precedence)
          const payload: ChatRequest = {
            ...req,
            model:   req.model   || this.settings.model(),
            api_key: req.api_key || this.settings.apiKey(),
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

            for (const line of lines) {
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
