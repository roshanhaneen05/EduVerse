import { FormBuilder } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthResponse, User } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let router: jasmine.SpyObj<Router>;
  let route: ActivatedRoute;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['login', 'instructorLogin']);
    router = jasmine.createSpyObj<Router>('Router', ['navigateByUrl']);
    route = { snapshot: { data: {} } } as ActivatedRoute;
    component = new LoginComponent(new FormBuilder(), auth, router, route);
    component.loginForm.setValue({
      email: 'person@eduverse.io',
      password: 'SecurePassword123!'
    });
  });

  it('redirects each database role to its matching dashboard', () => {
    const destinations: Record<User['role'], string> = {
      student: '/student/dashboard',
      instructor: '/instructor/dashboard',
      admin: '/admin/dashboard'
    };

    for (const role of Object.keys(destinations) as User['role'][]) {
      const user: User = {
        id: 1,
        email: 'person@eduverse.io',
        full_name: 'EduVerse User',
        role,
        is_active: true,
        created_at: '',
        updated_at: ''
      };
      const response: AuthResponse = {
        access_token: 'test-token',
        token_type: 'bearer',
        expires_in_minutes: 30,
        user
      };
      auth.login.and.returnValue(of(response));

      component.onSubmit();

      expect(router.navigateByUrl).toHaveBeenCalledWith(destinations[role]);
    }
  });

  it('passes credentials and remember-me preference to the authentication service', () => {
    const user: User = {
      id: 1,
      email: 'person@eduverse.io',
      full_name: 'EduVerse User',
      role: 'student',
      is_active: true,
      created_at: '',
      updated_at: ''
    };
    auth.login.and.returnValue(of({
      access_token: 'test-token',
      token_type: 'bearer',
      expires_in_minutes: 30,
      user
    }));
    component.rememberMe = false;

    component.onSubmit();

    expect(auth.login).toHaveBeenCalledWith(
      { email: 'person@eduverse.io', password: 'SecurePassword123!' },
      false
    );
  });

  it('uses the instructor-only authentication endpoint on the instructor sign-in route', () => {
    const user: User = {
      id: 2,
      email: 'faculty@eduverse.io',
      full_name: 'Faculty Member',
      role: 'instructor',
      is_active: true,
      created_at: '',
      updated_at: ''
    };
    auth.instructorLogin.and.returnValue(of({
      access_token: 'instructor-token',
      token_type: 'bearer',
      expires_in_minutes: 30,
      user
    }));
    const instructorRoute = jasmine.createSpyObj<ActivatedRoute>('ActivatedRoute', ['toString']);
    Object.defineProperty(instructorRoute, 'snapshot', {
      value: { data: { role: 'instructor' } }
    });
    component = new LoginComponent(
      new FormBuilder(),
      auth,
      router,
      instructorRoute
    );
    component.loginForm.setValue({
      email: 'faculty@eduverse.io',
      password: 'SecurePassword123!'
    });

    component.onSubmit();

    expect(auth.instructorLogin).toHaveBeenCalledWith(
      { email: 'faculty@eduverse.io', password: 'SecurePassword123!' },
      true
    );
    expect(router.navigateByUrl).toHaveBeenCalledWith('/instructor/dashboard');
  });
});
