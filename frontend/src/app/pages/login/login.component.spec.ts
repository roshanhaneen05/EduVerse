import { FormBuilder } from '@angular/forms';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { AuthResponse, User } from '../../core/models/user.model';
import { AuthService } from '../../core/services/auth.service';
import { LoginComponent } from './login.component';

describe('LoginComponent', () => {
  let component: LoginComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let router: jasmine.SpyObj<Router>;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['login']);
    router = jasmine.createSpyObj<Router>('Router', ['navigateByUrl']);
    component = new LoginComponent(new FormBuilder(), auth, router);
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
});
