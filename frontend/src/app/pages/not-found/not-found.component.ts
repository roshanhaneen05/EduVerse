import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="not-found-page">
      <div class="not-found-card card">
        <div class="error-code">404</div>
        <h1>Page Not Found</h1>
        <p>The page or resource you are looking for has been moved, renamed, or does not exist in EduVerse.</p>
        <div class="actions">
          <a routerLink="/" class="btn btn-primary">Return to Home</a>
          <a routerLink="/courses" class="btn btn-secondary">Explore Catalog</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .not-found-page {
      min-height: calc(100vh - 160px);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 2rem;
      background-color: var(--bg-app);
    }
    .not-found-card {
      max-width: 500px;
      width: 100%;
      text-align: center;
      padding: 3rem 2rem;
    }
    .error-code {
      font-size: 5rem;
      font-weight: 800;
      color: var(--primary);
      line-height: 1;
      margin-bottom: 1rem;
    }
    .not-found-card h1 {
      font-size: 1.75rem;
      margin-bottom: 0.75rem;
    }
    .not-found-card p {
      color: var(--text-muted);
      font-size: 1rem;
      margin-bottom: 2rem;
      line-height: 1.6;
    }
    .actions {
      display: flex;
      justify-content: center;
      gap: 1rem;
    }
  `]
})
export class NotFoundComponent {}

