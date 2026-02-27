import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, inject, signal
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '../../../core/services/settings.service';
import { ToastService } from '../../../core/services/toast.service';

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
  imports: [CommonModule, FormsModule],
  templateUrl: './settings-panel.component.html',
})
export class SettingsPanelComponent implements OnChanges {
  @Input() open = false;
  @Output() closed = new EventEmitter<void>();

  private settings = inject(SettingsService);
  private toast    = inject(ToastService);

  presetModels = PRESET_MODELS;

  draftModel    = '';
  draftApiKey   = '';
  draftProvider = '';
  showKey       = false;
  saving        = signal(false);
  saveError     = signal('');

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open']?.currentValue) {
      this.draftModel    = this.settings.model();
      this.draftApiKey   = this.settings.apiKey();
      this.draftProvider = this.settings.openrouterProvider();
      this.showKey       = false;
      this.saveError.set('');
    }
  }

  toggleShowKey(): void {
    this.showKey = !this.showKey;
  }

  get canSave(): boolean {
    return !!this.draftModel.trim() && !!this.draftApiKey.trim() && !this.saving();
  }

  save(): void {
    if (!this.canSave) return;
    this.saving.set(true);
    this.saveError.set('');
    this.settings.saveSettings(this.draftModel.trim(), this.draftApiKey.trim(), this.draftProvider.trim()).subscribe({
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
