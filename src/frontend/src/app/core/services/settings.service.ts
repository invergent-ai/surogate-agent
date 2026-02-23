import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly MODEL_KEY   = 'surogate_model';
  private readonly API_KEY_KEY = 'surogate_api_key';

  model  = signal<string>(localStorage.getItem(this.MODEL_KEY)   || 'claude-sonnet-4-6');
  apiKey = signal<string>(localStorage.getItem(this.API_KEY_KEY) || '');

  saveModel(m: string): void {
    const val = m.trim() || 'claude-sonnet-4-6';
    this.model.set(val);
    localStorage.setItem(this.MODEL_KEY, val);
  }

  saveApiKey(key: string): void {
    const val = key.trim();
    this.apiKey.set(val);
    if (val) {
      localStorage.setItem(this.API_KEY_KEY, val);
    } else {
      localStorage.removeItem(this.API_KEY_KEY);
    }
  }
}
