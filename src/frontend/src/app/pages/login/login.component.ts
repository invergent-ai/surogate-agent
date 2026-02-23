import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterModule } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  templateUrl: './login.component.html',
})
export class LoginComponent {
  private auth = inject(AuthService);
  private router = inject(Router);

  username = signal('');
  password = signal('');
  loading  = signal(false);
  error    = signal('');

  submit(): void {
    const u = this.username().trim();
    const p = this.password();
    if (!u || !p) return;

    this.loading.set(true);
    this.error.set('');

    this.auth.login({ username: u, password: p }).subscribe({
      next: () => {
        const role = this.auth.currentUser()?.role;
        this.router.navigate([role === 'developer' ? '/developer' : '/user']);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Login failed. Please try again.');
        this.loading.set(false);
      },
    });
  }
}
