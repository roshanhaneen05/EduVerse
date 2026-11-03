import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthService } from '../services/auth.service';

export const roleGuard: CanActivateFn = (route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (!authService.isAuthenticated()) {
    return router.createUrlTree(['/login'], { queryParams: { returnUrl: state.url } });
  }

  const expectedRoles = route.data?.['roles'] as string[] | undefined;
  if (!expectedRoles || expectedRoles.length === 0) {
    return true;
  }

  const currentUser = authService.currentUser();
  if (currentUser && (expectedRoles.includes(currentUser.role) || currentUser.role === 'admin')) {
    return true;
  }

  // Not authorized: redirect to root or student dashboard
  return router.createUrlTree(['/student/dashboard']);
};

