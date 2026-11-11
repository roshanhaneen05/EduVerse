import { Component } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';

type AccountRole = 'student' | 'instructor' | 'admin';

@Component({
  selector: 'app-account-selection',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="selection-page">
      <header class="selection-header">
        <a routerLink="/" class="brand" aria-label="EduVerse home">
          <span class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 32 32" fill="none">
              <path d="M16 4 2 11l14 7 14-7-14-7Z" fill="currentColor"/>
              <path d="M6 14.5V21c0 3.5 4.5 6.5 10 6.5s10-3 10-6.5v-6.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
            </svg>
          </span>
          <span>Edu<span>Verse</span></span>
        </a>
        <a routerLink="/" class="back-home">Back to home</a>
      </header>

      <main class="selection-main">
        <div class="selection-heading">
          <span class="eyebrow">WELCOME TO EDUVERSE</span>
          <h1>{{ isRegisterMode ? 'Choose your account type' : 'How will you use EduVerse?' }}</h1>
          <p>{{ isRegisterMode ? 'Choose Student or Instructor to create your EduVerse account.' : 'Choose your account type to continue to your secure sign in.' }}</p>
        </div>

        <div class="account-grid" [class.registration-grid]="isRegisterMode">
          @for (account of visibleAccounts; track account.role) {
            <article class="account-card" [class]="account.role">
              <div class="account-icon" aria-hidden="true">
                @if (account.role === 'student') {
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="m2 9 10-5 10 5-10 5L2 9Z"/>
                    <path d="M6 11v5c3.5 3 8.5 3 12 0v-5M22 9v6"/>
                  </svg>
                } @else if (account.role === 'instructor') {
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="4" width="18" height="13" rx="2"/>
                    <path d="M8 21h8M12 17v4M8 9h8M8 13h5"/>
                  </svg>
                } @else {
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M12 3 4 6v5c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V6l-8-3Z"/>
                    <path d="m9 12 2 2 4-4"/>
                  </svg>
                }
              </div>
              <span class="role-label">{{ account.label }}</span>
              <h2>{{ account.title }}</h2>
              <p>{{ isRegisterMode ? account.registerDescription : account.description }}</p>
              <a
                class="account-button"
                [routerLink]="['/', account.role, isRegisterMode ? 'register' : 'login']"
                [queryParams]="returnUrl ? { returnUrl } : null"
              >
                {{ isRegisterMode ? 'Register as ' + account.title : account.button }}
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M5 12h14M13 6l6 6-6 6"/>
                </svg>
              </a>
            </article>
          }
        </div>

        <p class="selection-note">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="4" y="10" width="16" height="11" rx="2"/>
            <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>
          </svg>
          Your account is protected with secure, role-based access.
        </p>
      </main>
      <footer class="selection-footer">© 2026 EduVerse. Learning without limits.</footer>
    </div>
  `,
  styles: [`
    :host { display: block; min-height: 100vh; }
    .selection-page {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      color: #1e1b4b;
      background:
        radial-gradient(ellipse at 12% 18%, rgba(221, 214, 254, .55), transparent 34rem),
        linear-gradient(145deg, #fcfbff 0%, #f5f2ff 55%, #efecff 100%);
    }
    .selection-header {
      width: min(1200px, calc(100% - 3rem));
      margin: 0 auto;
      min-height: 88px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }
    .brand {
      display: inline-flex;
      align-items: center;
      gap: .65rem;
      color: #1e1b4b;
      font-size: 1.45rem;
      font-weight: 800;
      letter-spacing: -.04em;
    }
    .brand > span:last-child span { color: #6558d9; }
    .brand-mark { width: 34px; height: 34px; color: #5b50d6; }
    .brand-mark svg { width: 100%; height: 100%; }
    .back-home { color: #64708a; font-size: .9rem; font-weight: 650; }
    .back-home:hover { color: #4f46e5; }
    .selection-main {
      width: min(1100px, calc(100% - 3rem));
      margin: auto;
      padding: 3.5rem 0 4rem;
    }
    .selection-heading { text-align: center; margin-bottom: 2.7rem; }
    .eyebrow {
      display: inline-flex;
      color: #6258cb;
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .14em;
      margin-bottom: .85rem;
    }
    .selection-heading h1 {
      font-size: clamp(2rem, 4vw, 3rem);
      letter-spacing: -.045em;
      margin: 0 0 .75rem;
    }
    .selection-heading p { color: #667085; font-size: 1.02rem; margin: 0; }
    .account-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1.25rem; }
    .account-grid.registration-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); max-width: 760px; margin: 0 auto; }
    .account-card {
      --role-color: #5b50d6;
      --role-soft: #f0eeff;
      position: relative;
      display: flex;
      flex-direction: column;
      min-height: 345px;
      padding: 2rem;
      background: rgba(255,255,255,.88);
      border: 1px solid #e8e5f7;
      border-radius: 22px;
      box-shadow: 0 18px 48px rgba(58, 48, 122, .07);
      transition: transform .22s ease, box-shadow .22s ease, border-color .22s ease;
      animation: rise-in .55s both;
    }
    .account-card:nth-child(2) { animation-delay: .08s; }
    .account-card:nth-child(3) { animation-delay: .16s; }
    .account-card:hover { transform: translateY(-6px); border-color: #c9c3f4; box-shadow: 0 24px 55px rgba(58,48,122,.13); }
    .account-card.instructor { --role-color: #7354bf; --role-soft: #f4edff; }
    .account-card.admin { --role-color: #4e5e9d; --role-soft: #edf2ff; }
    .account-icon {
      width: 58px;
      height: 58px;
      display: grid;
      place-items: center;
      color: var(--role-color);
      background: var(--role-soft);
      border-radius: 17px;
      margin-bottom: 1.5rem;
    }
    .account-icon svg { width: 30px; height: 30px; }
    .role-label { color: var(--role-color); font-size: .69rem; font-weight: 800; letter-spacing: .13em; }
    .account-card h2 { font-size: 1.45rem; letter-spacing: -.03em; margin: .4rem 0 .65rem; }
    .account-card p { color: #68738a; font-size: .91rem; line-height: 1.7; margin: 0 0 1.8rem; }
    .account-button {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: .65rem;
      margin-top: auto;
      padding: .85rem 1rem;
      color: #fff;
      background: linear-gradient(135deg, var(--role-color), #7568e6);
      border-radius: 11px;
      font-size: .88rem;
      font-weight: 750;
      box-shadow: 0 8px 18px color-mix(in srgb, var(--role-color) 20%, transparent);
      transition: filter .2s ease, transform .2s ease;
    }
    .account-button:hover { color: #fff; filter: brightness(.94); transform: translateY(-1px); }
    .account-button svg { width: 17px; height: 17px; }
    .selection-note {
      display: flex;
      justify-content: center;
      align-items: center;
      gap: .5rem;
      margin: 2rem 0 0;
      color: #788198;
      font-size: .82rem;
    }
    .selection-note svg { width: 17px; height: 17px; color: #7165d8; }
    .selection-footer { padding: 1.4rem; text-align: center; color: #8a90a4; font-size: .78rem; }
    @keyframes rise-in { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
    @media (max-width: 820px) {
      .selection-main { padding-top: 2.5rem; }
      .account-grid { grid-template-columns: 1fr; max-width: 540px; margin: 0 auto; }
      .account-grid.registration-grid { grid-template-columns: 1fr; }
      .account-card { min-height: 0; padding: 1.6rem; }
      .account-icon { margin-bottom: 1rem; }
    }
    @media (max-width: 480px) {
      .selection-header, .selection-main { width: min(100% - 2rem, 1100px); }
      .selection-header { min-height: 72px; }
      .selection-heading { margin-bottom: 2rem; }
      .selection-note { align-items: flex-start; text-align: center; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: .01ms !important; transition-duration: .01ms !important; }
    }
  `]
})
export class AccountSelectionComponent {
  readonly returnUrl: string | undefined;
  readonly isRegisterMode: boolean;

  readonly accounts: {
    role: AccountRole;
    label: string;
    title: string;
    description: string;
    registerDescription: string;
    button: string;
  }[] = [
    {
      role: 'student',
      label: 'LEARN & GROW',
      title: 'Student',
      description: 'Access courses, track learning progress and complete assignments.',
      registerDescription: 'Create a student account to explore courses and track your learning progress.',
      button: 'Student Login'
    },
    {
      role: 'instructor',
      label: 'TEACH & INSPIRE',
      title: 'Instructor',
      description: 'Manage courses, create lessons and monitor student progress.',
      registerDescription: 'Create an instructor account to share your expertise and manage courses.',
      button: 'Instructor Login'
    },
    {
      role: 'admin',
      label: 'PLATFORM ACCESS',
      title: 'Admin',
      description: 'Manage users, courses and the complete EduVerse platform.',
      registerDescription: '',
      button: 'Admin Login'
    }
  ];

  get visibleAccounts() {
    return this.isRegisterMode ? this.accounts.filter(account => account.role !== 'admin') : this.accounts;
  }

  constructor(private route: ActivatedRoute) {
    this.returnUrl = this.route.snapshot.queryParams['returnUrl'] as string | undefined;
    this.isRegisterMode = this.route.snapshot.data['mode'] === 'register';
  }
}
