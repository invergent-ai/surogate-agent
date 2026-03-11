/**
 * Reusable LLM configuration component.
 *
 * Encapsulates: vLLM URL, model selector, thinking toggle, API key,
 * OpenRouter provider, and the full vLLM advanced settings sub-panel.
 *
 * Usage:
 *   <app-model-keys [(config)]="myConfig" />
 *
 * Emits `configChange` whenever any field changes.
 */
import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges,
  inject, signal, ElementRef, HostListener,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { AuthService } from '../../../core/services/auth.service';
import { ApiConfigService } from '../../../core/services/api-config.service';

export interface ModelKeysConfig {
  model: string;
  api_key: string;
  openrouter_provider: string;
  vllm_url: string;
  vllm_tool_calling: boolean;
  vllm_temperature: number | null;
  vllm_top_k: number | null;
  vllm_top_p: number | null;
  vllm_min_p: number | null;
  vllm_presence_penalty: number | null;
  vllm_context_length: number | null;
  thinking_enabled: boolean;
  thinking_budget: number;
}

export function emptyModelKeysConfig(): ModelKeysConfig {
  return {
    model: '', api_key: '', openrouter_provider: '',
    vllm_url: '', vllm_tool_calling: true,
    vllm_temperature: null, vllm_top_k: null, vllm_top_p: null,
    vllm_min_p: null, vllm_presence_penalty: null, vllm_context_length: null,
    thinking_enabled: false, thinking_budget: 10000,
  };
}

export const PRESET_MODELS = [
  'claude-opus-4-6',
  'claude-sonnet-4-6',
  'claude-haiku-4-5-20251001',
  'gpt-5.2',
  'gpt-4o',
  'gpt-4.1',
  'o3',
  'o4-mini',
  'minimax/MiniMax-M2.5',
];

@Component({
  selector: 'app-model-keys',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './model-keys.component.html',
})
export class ModelKeysComponent implements OnChanges {
  @Input() config: ModelKeysConfig = emptyModelKeysConfig();
  @Output() configChange = new EventEmitter<ModelKeysConfig>();

  private http   = inject(HttpClient);
  private auth   = inject(AuthService);
  private apiCfg = inject(ApiConfigService);
  private elRef  = inject(ElementRef);

  presetModels = PRESET_MODELS;
  showKey = false;

  vllmModels        = signal<string[]>([]);
  fetchingModels    = signal(false);
  fetchModelsError  = signal('');
  vllmAdvancedOpen  = signal(false);
  modelDropdownOpen = signal(false);

  @HostListener('document:click', ['$event'])
  onDocumentClick(e: MouseEvent): void {
    if (!this.elRef.nativeElement.contains(e.target)) {
      this.modelDropdownOpen.set(false);
    }
  }

  get useVllm(): boolean { return !!this.config.vllm_url?.trim(); }

  get displayedModels(): string[] {
    return this.useVllm ? this.vllmModels() : this.presetModels;
  }

  get filteredModels(): string[] {
    const q = this.config.model.trim().toLowerCase();
    const all = this.displayedModels;
    return q ? all.filter(m => m.toLowerCase().includes(q)) : all;
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['config']) {
      const prev = changes['config'].previousValue as ModelKeysConfig | undefined;
      const curr = changes['config'].currentValue as ModelKeysConfig;
      if (prev?.vllm_url !== curr.vllm_url) {
        this.vllmModels.set([]);
        this.fetchModelsError.set('');
        this.vllmAdvancedOpen.set(false);
        if (curr.vllm_url?.trim()) {
          this.fetchVllmModels();
        }
      }
    }
  }

  fetchVllmModels(): void {
    const url = this.config.vllm_url?.trim();
    if (!url) return;
    this.fetchingModels.set(true);
    this.fetchModelsError.set('');
    this.vllmModels.set([]);
    this.vllmAdvancedOpen.set(false);
    const token = this.auth.token();
    const headers = token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : undefined;
    this.http.get<string[]>(`${this.apiCfg.apiUrl}/vllm/models`, { headers, params: { url } }).subscribe({
      next: (ids) => {
        this.fetchingModels.set(false);
        this.vllmModels.set(ids);
        if (ids.length > 0 && !this.config.model) {
          this.update('model', ids[0]);
        }
      },
      error: (err) => {
        this.fetchingModels.set(false);
        this.fetchModelsError.set(err?.error?.detail ?? 'Could not reach endpoint.');
      },
    });
  }

  selectModel(model: string): void {
    this.update('model', model);
    this.modelDropdownOpen.set(false);
  }

  update(field: keyof ModelKeysConfig, value: unknown): void {
    this.config = { ...this.config, [field]: value };
    this.configChange.emit(this.config);
  }

  toggleShowKey(): void { this.showKey = !this.showKey; }
}
