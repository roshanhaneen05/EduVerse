import { FormBuilder } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { RegisterComponent } from './register.component';

describe('RegisterComponent', () => {
  let component: RegisterComponent;
  let auth: jasmine.SpyObj<AuthService>;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['register', 'login']);
    const router = jasmine.createSpyObj<Router>('Router', ['navigate']);
    const route = jasmine.createSpyObj<ActivatedRoute>('ActivatedRoute', ['toString']);
    Object.defineProperty(route, 'snapshot', {
      value: { data: { role: 'instructor' } }
    });
    component = new RegisterComponent(new FormBuilder(), auth, router, route);
    component.ngOnInit();
    component.registerForm.setValue({
      full_name: 'Test Instructor',
      email: 'test.instructor@example.com',
      password: 'SecurePassword123!',
      confirm_password: 'SecurePassword123!'
    });
  });

  it('explains when the backend cannot be reached', () => {
    auth.register.and.returnValue(throwError(() => ({ status: 0 })));

    component.onSubmit();

    expect(component.errorMessage).toContain('Unable to connect to the EduVerse backend');
  });

  it('shows the backend reason when registration is rejected', () => {
    auth.register.and.returnValue(
      throwError(() => ({ status: 409, error: { detail: 'An account with this email address already exists.' } }))
    );

    component.onSubmit();

    expect(component.errorMessage).toBe('An account with this email address already exists.');
  });
});
