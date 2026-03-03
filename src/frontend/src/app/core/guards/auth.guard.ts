import { CanActivateFn } from '@angular/router';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const authGuard: CanActivateFn = (route) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!auth.isAuthenticated()) {
    router.navigate(['/login']);
    return false;
  }

  const requiredRole = route.data?.['role'] as string | undefined;
  if (requiredRole) {
    const userRole = auth.currentUser()?.role;
    if (userRole !== requiredRole) {
      router.navigate([userRole === 'developer' ? '/developer' : '/user']);
      return false;
    }
  }

  return true;
};
