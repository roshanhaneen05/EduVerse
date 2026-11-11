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
  if (currentUser && expectedRoles.includes(currentUser.role)) {
    return true;
  }

  const roleDashboard: Record<string, string> = {
    student: '/student/dashboard',
    instructor: '/instructor/dashboard',
    admin: '/admin/dashboard'
  };
  return router.createUrlTree([roleDashboard[currentUser?.role ?? ''] ?? '/']);
};
