import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { SettingsService } from '../../../core/services/settings.service';
import { ToastService } from '../../../core/services/toast.service';
import { ApiConfigService } from '../../../core/services/api-config.service';
import { AuthService } from '../../../core/services/auth.service';
import { McpPanelComponent } from '../mcp-panel/mcp-panel.component';

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
  selector: 'app-settings-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, McpPanelComponent],
  templateUrl: './settings-panel.component.html',
})
export class SettingsPanelComponent implements OnChanges {
  @Input() open = false;
  @Output() closed = new EventEmitter<void>();

  private settings = inject(SettingsService);
  private toast    = inject(ToastService);
  private http     = inject(HttpClient);
  private config   = inject(ApiConfigService);
  auth             = inject(AuthService);

  presetModels = PRESET_MODELS;

  activeTab: 'settings' | 'mcp' = 'settings';

  draftModel              = '';
  draftApiKey             = '';
  draftProvider           = '';
  draftVllmUrl            = '';
  draftVllmToolCalling    = true;
  draftVllmTemperature    = '';
  draftVllmTopK           = '';
  draftVllmTopP           = '';
  draftVllmMinP           = '';
  draftVllmPresencePenalty = '';
  draftVllmContextLength   = '';
  draftThinkingEnabled     = false;
  draftThinkingBudget      = '10000';
  showKey       = false;
  saving        = signal(false);
  saveError     = signal('');

  // vLLM model list fetched from the endpoint
  vllmModels       = signal<string[]>([]);
  fetchingModels   = signal(false);
  fetchModelsError = signal('');
  vllmAdvancedOpen = signal(false);

  get useVllm(): boolean {
    return !!this.draftVllmUrl.trim();
  }

  get displayedModels(): string[] {
    return this.useVllm ? this.vllmModels() : this.presetModels;
  }

  private _numToStr(v: number | null): string {
    return v !== null && v !== undefined ? String(v) : '';
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open']?.currentValue) {
      this.draftModel               = this.settings.model();
      this.draftApiKey              = this.settings.apiKey();
      this.draftProvider            = this.settings.openrouterProvider();
      this.draftVllmUrl             = this.settings.vllmUrl();
      this.draftVllmToolCalling     = this.settings.vllmToolCalling();
      this.draftVllmTemperature     = this._numToStr(this.settings.vllmTemperature());
      this.draftVllmTopK            = this._numToStr(this.settings.vllmTopK());
      this.draftVllmTopP            = this._numToStr(this.settings.vllmTopP());
      this.draftVllmMinP            = this._numToStr(this.settings.vllmMinP());
      this.draftVllmPresencePenalty = this._numToStr(this.settings.vllmPresencePenalty());
      this.draftVllmContextLength   = this._numToStr(this.settings.vllmContextLength());
      this.draftThinkingEnabled     = this.settings.thinkingEnabled();
      this.draftThinkingBudget      = this._numToStr(this.settings.thinkingBudget()) || '10000';
      this.showKey                  = false;
      this.saveError.set('');
      this.fetchModelsError.set('');
      this.vllmAdvancedOpen.set(false);
      this.activeTab = 'settings';
      // Pre-load models if URL already set
      if (this.draftVllmUrl.trim()) {
        this.fetchVllmModels();
      }
    }
  }

  toggleShowKey(): void {
    this.showKey = !this.showKey;
  }

  fetchVllmModels(): void {
    const url = this.draftVllmUrl.trim();
    if (!url) return;
    this.fetchingModels.set(true);
    this.fetchModelsError.set('');
    this.vllmModels.set([]);
    this.vllmAdvancedOpen.set(false);
    const token = this.auth.token();
    const headers = token ? new HttpHeaders({ Authorization: `Bearer ${token}` }) : undefined;
    this.http.get<string[]>(
      `${this.config.apiUrl}/vllm/models`,
      { headers, params: { url } },
    ).subscribe({
      next: (ids) => {
        this.fetchingModels.set(false);
        this.vllmModels.set(ids);
        if (ids.length > 0 && !this.draftModel) {
          this.draftModel = ids[0];
        }
      },
      error: (err) => {
        this.fetchingModels.set(false);
        const detail = err?.error?.detail ?? 'Could not reach endpoint. Check the URL.';
        this.fetchModelsError.set(detail);
      },
    });
  }

  get canSave(): boolean {
    const hasModel = !!this.draftModel.trim();
    const hasKey   = !!this.draftApiKey.trim();
    const hasVllm  = !!this.draftVllmUrl.trim();
    // API key is optional when a vLLM URL is provided
    return hasModel && (hasVllm || hasKey) && !this.saving();
  }

  private _parseFloat(s: string | number | null | undefined): number | null {
    if (s === null || s === undefined || s === '') return null;
    const v = parseFloat(String(s).trim());
    return isNaN(v) ? null : v;
  }

  private _parseInt(s: string | number | null | undefined): number | null {
    if (s === null || s === undefined || s === '') return null;
    const v = parseInt(String(s).trim(), 10);
    return isNaN(v) ? null : v;
  }

  save(): void {
    if (!this.canSave) return;
    this.saving.set(true);
    this.saveError.set('');
    this.settings.saveSettings(
      this.draftModel.trim(),
      this.draftApiKey.trim(),
      this.draftProvider.trim(),
      this.draftVllmUrl.trim(),
      this.draftVllmToolCalling,
      this._parseFloat(this.draftVllmTemperature),
      this._parseInt(this.draftVllmTopK),
      this._parseFloat(this.draftVllmTopP),
      this._parseFloat(this.draftVllmMinP),
      this._parseFloat(this.draftVllmPresencePenalty),
      this._parseInt(this.draftVllmContextLength),
      this.draftThinkingEnabled,
      this._parseInt(this.draftThinkingBudget) ?? 10000,
    ).subscribe({
      next: () => {
        this.saving.set(false);
        this.toast.success('Settings saved');
        this.closed.emit();
      },
      error: () => {
        this.saving.set(false);
        this.saveError.set('Failed to save. Please try again.');
      },
    });
  }

  cancel(): void {
    this.closed.emit();
  }

  onBackdropClick(e: MouseEvent): void {
    if ((e.target as HTMLElement).classList.contains('settings-backdrop')) {
      this.cancel();
    }
  }
}
