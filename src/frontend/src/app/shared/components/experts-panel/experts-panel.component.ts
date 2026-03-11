import {
  Component, OnInit, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ExpertService } from '../../../core/services/expert.service';
import { SettingsService } from '../../../core/services/settings.service';
import { ToastService } from '../../../core/services/toast.service';
import { ConfirmDialogService } from '../../../core/services/confirm-dialog.service';
import { Expert, ExpertCreateRequest, emptyExpertRequest } from '../../../core/models/expert.models';
import { ModelKeysComponent, ModelKeysConfig, emptyModelKeysConfig } from '../model-keys/model-keys.component';

@Component({
  selector: 'app-experts-panel',
  standalone: true,
  imports: [CommonModule, FormsModule, ModelKeysComponent],
  templateUrl: './experts-panel.component.html',
})
export class ExpertsPanelComponent implements OnInit {
  private expertSvc   = inject(ExpertService);
  private settings    = inject(SettingsService);
  private confirmSvc  = inject(ConfirmDialogService);
  private toast     = inject(ToastService);

  experts     = signal<Expert[]>([]);
  loading     = signal(false);
  saving      = signal(false);
  saveError   = signal('');

  // Expert lookup toggle (for skill-developer)
  expertLookupEnabled = signal(false);
  savingToggle = signal(false);

  // Form state
  editingId   = signal<number | null>(null);  // null = creating new
  showForm    = signal(false);

  draftName        = '';
  draftDescription = '';
  draftLlmConfig: ModelKeysConfig = emptyModelKeysConfig();
  draftAvailableTools    = '';
  draftAvailableSkills   = '';
  draftAvailableMcp      = '';

  ngOnInit(): void {
    this.expertLookupEnabled.set(this.settings.expertLookupEnabled());
    this.loadExperts();
  }

  loadExperts(): void {
    this.loading.set(true);
    this.expertSvc.list().subscribe({
      next: (list) => { this.experts.set(list); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  openCreate(): void {
    this.editingId.set(null);
    this.draftName = '';
    this.draftDescription = '';
    this.draftLlmConfig = emptyModelKeysConfig();
    this.draftAvailableTools = '';
    this.draftAvailableSkills = '';
    this.draftAvailableMcp = '';
    this.saveError.set('');
    this.showForm.set(true);
  }

  openEdit(expert: Expert): void {
    this.editingId.set(expert.id);
    this.draftName = expert.name;
    this.draftDescription = expert.description;
    this.draftLlmConfig = {
      model: expert.model,
      api_key: expert.api_key,
      openrouter_provider: expert.openrouter_provider,
      vllm_url: expert.vllm_url,
      vllm_tool_calling: expert.vllm_tool_calling,
      vllm_temperature: expert.vllm_temperature,
      vllm_top_k: expert.vllm_top_k,
      vllm_top_p: expert.vllm_top_p,
      vllm_min_p: expert.vllm_min_p,
      vllm_presence_penalty: expert.vllm_presence_penalty,
      vllm_context_length: expert.vllm_context_length,
      thinking_enabled: expert.thinking_enabled,
      thinking_budget: expert.thinking_budget,
    };
    this.draftAvailableTools = (expert.available_tools || []).join(', ');
    this.draftAvailableSkills = (expert.available_skills || []).join(', ');
    this.draftAvailableMcp = (expert.available_mcp_servers || []).join(', ');
    this.saveError.set('');
    this.showForm.set(true);
  }

  cancelForm(): void {
    this.showForm.set(false);
    this.editingId.set(null);
    this.saveError.set('');
  }

  private _splitList(s: string): string[] {
    return s.split(',').map(x => x.trim()).filter(Boolean);
  }

  private _buildRequest(): ExpertCreateRequest {
    return {
      name: this.draftName.trim(),
      description: this.draftDescription.trim(),
      model: this.draftLlmConfig.model,
      api_key: this.draftLlmConfig.api_key,
      openrouter_provider: this.draftLlmConfig.openrouter_provider,
      vllm_url: this.draftLlmConfig.vllm_url,
      vllm_tool_calling: this.draftLlmConfig.vllm_tool_calling,
      vllm_temperature: this.draftLlmConfig.vllm_temperature,
      vllm_top_k: this.draftLlmConfig.vllm_top_k,
      vllm_top_p: this.draftLlmConfig.vllm_top_p,
      vllm_min_p: this.draftLlmConfig.vllm_min_p,
      vllm_presence_penalty: this.draftLlmConfig.vllm_presence_penalty,
      vllm_context_length: this.draftLlmConfig.vllm_context_length,
      thinking_enabled: this.draftLlmConfig.thinking_enabled,
      thinking_budget: this.draftLlmConfig.thinking_budget,
      available_tools: this._splitList(this.draftAvailableTools),
      available_skills: this._splitList(this.draftAvailableSkills),
      available_mcp_servers: this._splitList(this.draftAvailableMcp),
    };
  }

  get canSave(): boolean {
    const hasModel = !!this.draftLlmConfig.model?.trim();
    const hasKey   = !!this.draftLlmConfig.api_key?.trim();
    const hasVllm  = !!this.draftLlmConfig.vllm_url?.trim();
    return !!this.draftName.trim() && hasModel && (hasVllm || hasKey) && !this.saving();
  }

  save(): void {
    if (!this.canSave) return;
    this.saving.set(true);
    this.saveError.set('');
    const req = this._buildRequest();
    const id = this.editingId();

    const op = id !== null
      ? this.expertSvc.update(id, req)
      : this.expertSvc.create(req);

    op.subscribe({
      next: () => {
        this.saving.set(false);
        this.showForm.set(false);
        this.toast.success(id !== null ? 'Expert updated' : 'Expert created');
        this.loadExperts();
      },
      error: (err) => {
        this.saving.set(false);
        this.saveError.set(err?.error?.detail ?? 'Failed to save expert.');
      },
    });
  }

  async delete(expert: Expert): Promise<void> {
    const ok = await this.confirmSvc.confirm(
      `Delete expert '${expert.name}'? This cannot be undone.`,
      { actionLabel: 'Delete' },
    );
    if (!ok) return;
    this.expertSvc.delete(expert.id).subscribe({
      next: () => {
        this.toast.success(`Expert '${expert.name}' deleted`);
        this.loadExperts();
      },
      error: () => this.toast.error('Failed to delete expert.'),
    });
  }

  toggleExpertLookup(): void {
    const newVal = !this.expertLookupEnabled();
    this.savingToggle.set(true);
    this.settings.saveSettings(
      this.settings.model(),
      this.settings.apiKey(),
      this.settings.openrouterProvider(),
      this.settings.vllmUrl(),
      this.settings.vllmToolCalling(),
      this.settings.vllmTemperature(),
      this.settings.vllmTopK(),
      this.settings.vllmTopP(),
      this.settings.vllmMinP(),
      this.settings.vllmPresencePenalty(),
      this.settings.vllmContextLength(),
      this.settings.thinkingEnabled(),
      this.settings.thinkingBudget(),
      newVal,
    ).subscribe({
      next: () => {
        this.expertLookupEnabled.set(newVal);
        this.savingToggle.set(false);
      },
      error: () => this.savingToggle.set(false),
    });
  }
}
