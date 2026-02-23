import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ValidationResult } from '../../../core/models/skill.models';

@Component({
  selector: 'app-validation-badge',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './validation-badge.component.html',
})
export class ValidationBadgeComponent {
  @Input() result: ValidationResult | null = null;
  @Input() loading = false;
}
