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
    <div class="app-layout" [class.is-standalone-page]="isStandalonePage()">
      @if (!isStandalonePage()) {
        <app-navbar></app-navbar>
      }
      <main class="app-content" [class.standalone-page]="isStandalonePage()">
        <router-outlet></router-outlet>
      </main>
      @if (!isStandalonePage()) {
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
    .app-content {
      flex: 1 0 auto;
      display: flex;
      flex-direction: column;
    }
    .app-content.standalone-page {
      display: block;
      flex: 1 0 auto;
      min-height: 100vh;
      overflow-x: hidden;
    }
    .app-layout.is-standalone-page {
      min-height: 100vh;
    }
  `]
})
export class AppComponent {
  title = 'EduVerse';
  private router = inject(Router);

  isStandalonePage = toSignal(
    this.router.events.pipe(
      filter(e => e instanceof NavigationEnd),
      map(() => this.checkStandalonePage())
    ),
    { initialValue: this.checkStandalonePage() }
  );

  private checkStandalonePage(): boolean {
    const p = window.location.pathname;
    return p === '/'
      || p === '/login'
      || p === '/student/login'
      || p === '/instructor/login'
      || p === '/admin/login';
  }
}
