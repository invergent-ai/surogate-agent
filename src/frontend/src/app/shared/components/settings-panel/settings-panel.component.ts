import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsService } from '../../../core/services/settings.service';

export const PRESET_MODELS = [
  'claude-opus-4-6',
  'claude-sonnet-4-6',
  'claude-haiku-4-5-20251001',
  'gpt-4o',
  'gpt-4o-mini',
  'gpt-4.1',
  'o3',
  'o4-mini',
  'gpt-5.2'
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

  presetModels = PRESET_MODELS;

  draftModel  = '';
  draftApiKey = '';
  showKey     = false;

  constructor(private settings: SettingsService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['open']?.currentValue) {
      this.draftModel  = this.settings.model();
      this.draftApiKey = this.settings.apiKey();
      this.showKey     = false;
    }
  }

  toggleShowKey(): void {
    this.showKey = !this.showKey;
  }

  save(): void {
    this.settings.saveModel(this.draftModel);
    this.settings.saveApiKey(this.draftApiKey);
    this.closed.emit();
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
