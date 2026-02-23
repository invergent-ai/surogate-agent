import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import {escapeHtml, extractApiErrorMessages } from '../../core/utils/error.utils';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './register.component.html',
})
export class RegisterComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  username = signal('');
  email    = signal('');
  password = signal('');
  confirm  = signal('');
  role     = signal<'developer' | 'user'>('user');
  loading  = signal(false);
  error    = signal('');

  submit(): void {
    if (this.password() !== this.confirm()) {
      this.error.set('Passwords do not match.');
      return;
    }

    this.loading.set(true);
    this.error.set('');

    this.auth.register({
      username: this.username().trim(),
      email:    this.email().trim(),
      password: this.password(),
      role:     this.role(),
    }).subscribe({
      next: () => {
        // Auto-login after registration
        this.auth.login({ username: this.username().trim(), password: this.password() }).subscribe({
          next: () => {
            const role = this.auth.currentUser()?.role;
            this.router.navigate([role === 'developer' ? '/developer' : '/user']);
          },
          error: () => this.router.navigate(['/login']),
        });
      },
      error: (err) => {
        const errors = extractApiErrorMessages(err, 'Registration failed. Please try again.');
        const errorHtml = `
          <ul class="list-disc pl-5 space-y-1">
            ${errors.map(m => `<li>${escapeHtml(m)}</li>`).join('')}
          </ul>
        `;
        this.error.set(errorHtml);
        this.loading.set(false);
      },
    });
  }
}

