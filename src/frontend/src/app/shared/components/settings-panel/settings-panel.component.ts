import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '../../../core/services/settings.service';
import { ToastService } from '../../../core/services/toast.service';
import { AuthService } from '../../../core/services/auth.service';
import { McpPanelComponent } from '../mcp-panel/mcp-panel.component';
import { ExpertsPanelComponent } from '../experts-panel/experts-panel.component';
import { ModelKeysComponent, ModelKeysConfig } from '../model-keys/model-keys.component';

@Component({
  selector: 'app-settings-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, McpPanelComponent, ExpertsPanelComponent, ModelKeysComponent],
  templateUrl: './settings-panel.component.html',
})
export class SettingsPanelComponent implements OnChanges {
  @Input() open = false;
  @Output() closed = new EventEmitter<void>();

  private settings = inject(SettingsService);
  private toast    = inject(ToastService);
  auth             = inject(AuthService);

  activeTab: 'settings' | 'mcp' | 'experts' = 'settings';

  draftConfig: ModelKeysConfig = {
    model: '', api_key: '', openrouter_provider: '',
    vllm_url: '', vllm_tool_calling: true,
    vllm_temperature: null, vllm_top_k: null, vllm_top_p: null,
    vllm_min_p: null, vllm_presence_penalty: null, vllm_context_length: null,
    thinking_enabled: false, thinking_budget: 10000,
  };

  saving    = signal(false);
  saveError = signal('');

  get canSave(): boolean {
    const hasModel = !!this.draftConfig.model?.trim();
    const hasKey   = !!this.draftConfig.api_key?.trim();
    const hasVllm  = !!this.draftConfig.vllm_url?.trim();
    return hasModel && (hasVllm || hasKey) && !this.saving();
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open']?.currentValue) {
      this.draftConfig = {
        model:                this.settings.model(),
        api_key:              this.settings.apiKey(),
        openrouter_provider:  this.settings.openrouterProvider(),
        vllm_url:             this.settings.vllmUrl(),
        vllm_tool_calling:    this.settings.vllmToolCalling(),
        vllm_temperature:     this.settings.vllmTemperature(),
        vllm_top_k:           this.settings.vllmTopK(),
        vllm_top_p:           this.settings.vllmTopP(),
        vllm_min_p:           this.settings.vllmMinP(),
        vllm_presence_penalty: this.settings.vllmPresencePenalty(),
        vllm_context_length:  this.settings.vllmContextLength(),
        thinking_enabled:     this.settings.thinkingEnabled(),
        thinking_budget:      this.settings.thinkingBudget() ?? 10000,
      };
      this.saveError.set('');
      this.activeTab = 'settings';
    }
  }

  save(): void {
    if (!this.canSave) return;
    this.saving.set(true);
    this.saveError.set('');
    const c = this.draftConfig;
    this.settings.saveSettings(
      c.model?.trim() ?? '',
      c.api_key?.trim() ?? '',
      c.openrouter_provider?.trim() ?? '',
      c.vllm_url?.trim() ?? '',
      c.vllm_tool_calling,
      c.vllm_temperature,
      c.vllm_top_k,
      c.vllm_top_p,
      c.vllm_min_p,
      c.vllm_presence_penalty,
      c.vllm_context_length,
      c.thinking_enabled,
      c.thinking_budget ?? 10000,
      this.settings.expertLookupEnabled(),
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


}
