import { Component, inject } from '@angular/core';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { CommonModule } from '@angular/common';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { NavbarComponent } from './layout/navbar/navbar.component';
import { FooterComponent } from './layout/footer/footer.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, NavbarComponent, FooterComponent, CommonModule],
  template: `
    <div class="app-layout" [class.is-auth-page]="isAuthPage()">
      @if (!isAuthPage()) {
        <app-navbar></app-navbar>
      }
      <main class="app-content" [class.no-nav]="isAuthPage()">
        <router-outlet></router-outlet>
      </main>
      @if (!isAuthPage()) {
        <app-footer></app-footer>
      }
    </div>
  `,
  styles: [`
    .app-layout {
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    .app-layout.is-auth-page {
      min-height: 100vh;
      height: 100vh;
      overflow-x: hidden;
    }
    .app-content {
      flex: 1 0 auto;
      display: flex;
      flex-direction: column;
    }
    .app-content.no-nav {
      flex: 1;
      min-height: 100vh;
      overflow-x: hidden;
    }
  `]
})
export class AppComponent {
  title = 'EduVerse';
  private router = inject(Router);

  isAuthPage = toSignal(
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      map(() => this.checkAuth())
    ),
    { initialValue: this.checkAuth() }
  );

  private checkAuth(): boolean {
    const p = window.location.pathname;
    return p === '/login' || p.startsWith('/login?');
  }
}
