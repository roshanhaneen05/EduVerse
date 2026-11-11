import { Injectable, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap, catchError, of } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthResponse, PasswordChange, User, UserUpdateProfile } from '../models/user.model';

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private readonly apiUrl = `${environment.apiUrl}/auth`;
  private readonly TOKEN_KEY = 'eduverse_token';
  private readonly USER_KEY = 'eduverse_user';

  // Signals for modern reactive state
  currentUser = signal<User | null>(this.getStoredUser());
  isAuthenticated = computed(() => !!this.currentUser());
  userRole = computed(() => this.currentUser()?.role || null);
  isAdmin = computed(() => this.currentUser()?.role === 'admin');
  isInstructor = computed(() => this.currentUser()?.role === 'instructor' || this.currentUser()?.role === 'admin');
  isStudent = computed(() => this.currentUser()?.role === 'student');

  constructor(
    private http: HttpClient,
    private router: Router
  ) {}

  private getStoredUser(): User | null {
    try {
      const data = localStorage.getItem(this.USER_KEY) ?? sessionStorage.getItem(this.USER_KEY);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY) ?? sessionStorage.getItem(this.TOKEN_KEY);
  }

  register(payload: { full_name: string; email: string; password: string; role?: string }): Observable<User> {
    return this.http.post<User>(`${this.apiUrl}/register`, payload);
  }

  login(payload: { email: string; password: string }, rememberMe = true): Observable<AuthResponse> {
    return this.http.post<AuthResponse>(`${this.apiUrl}/login`, {
      ...payload,
      remember_me: rememberMe
    }).pipe(
      tap(res => {
        const storage = rememberMe ? localStorage : sessionStorage;
        const otherStorage = rememberMe ? sessionStorage : localStorage;
        otherStorage.removeItem(this.TOKEN_KEY);
        otherStorage.removeItem(this.USER_KEY);
        storage.setItem(this.TOKEN_KEY, res.access_token);
        storage.setItem(this.USER_KEY, JSON.stringify(res.user));
        this.currentUser.set(res.user);
      })
    );
  }

  logout(): Observable<any> {
    return this.http.post(`${this.apiUrl}/logout`, {}).pipe(
      tap(() => this.clearSession()),
      catchError(() => {
        this.clearSession();
        return of(null);
      })
    );
  }

  clearSession(redirectToLogin = true): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    sessionStorage.removeItem(this.TOKEN_KEY);
    sessionStorage.removeItem(this.USER_KEY);
    this.currentUser.set(null);
    if (redirectToLogin) {
      this.router.navigate(['/login']);
    }
  }

  getMe(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/me`).pipe(
      tap(user => {
        this.getSessionStorage().setItem(this.USER_KEY, JSON.stringify(user));
        this.currentUser.set(user);
      })
    );
  }

  updateProfile(payload: UserUpdateProfile): Observable<User> {
    return this.http.put<User>(`${this.apiUrl}/profile`, payload).pipe(
      tap(user => {
        this.getSessionStorage().setItem(this.USER_KEY, JSON.stringify(user));
        this.currentUser.set(user);
      })
    );
  }

  changePassword(payload: PasswordChange): Observable<{ message: string }> {
    return this.http.put<{ message: string }>(`${this.apiUrl}/password`, payload);
  }

  hasRole(role: string): boolean {
    const current = this.currentUser();
    if (!current) return false;
    if (current.role === 'admin') return true; // Admin has super-access
    return current.role === role;
  }

  private getSessionStorage(): Storage {
    return localStorage.getItem(this.TOKEN_KEY) ? localStorage : sessionStorage;
  }
}
