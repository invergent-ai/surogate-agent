import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { ApiConfigService } from '../../core/services/api-config.service';
import { ThemeService } from '../../core/services/theme.service';

@Component({
  selector: 'app-entry',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './entry.component.html',
})
export class EntryComponent {
  private config = inject(ApiConfigService);
  private router = inject(Router);
  readonly theme = inject(ThemeService);
  userId = signal(this.config.userId());

  enter(role: 'developer' | 'user'): void {
    const id = this.userId().trim();
    if (!id) return;
    this.config.setUserId(id);
    this.router.navigate([`/${role}`]);
  }
}
