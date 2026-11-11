import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-footer',
  standalone: true,
  imports: [RouterLink],
  template: `
    <footer class="footer">
      <div class="footer-container">
        <div class="footer-top">
          <div class="footer-col brand-col">
            <div class="footer-brand">
              <span class="brand-name">Edu<span class="brand-accent">Verse</span></span>
            </div>
            <p class="brand-desc">
              Empowering learners and educators with modular curricula, comprehensive assessments, and intuitive platform management.
            </p>
            <div class="tech-stack-badges">
              <span class="pill">FastAPI</span>
              <span class="pill">Angular 19</span>
              <span class="pill">SQLAlchemy</span>
              <span class="pill">Argon2id</span>
            </div>
          </div>

          <div class="footer-col">
            <h4>Platform</h4>
            <ul>
              <li><a routerLink="/login">Sign In to Portal</a></li>
              <li><a routerLink="/student/register">Register Student Account</a></li>
              <li><a routerLink="/instructor/register">Register as Instructor</a></li>
            </ul>
          </div>

          <div class="footer-col">
            <h4>Security & Ops</h4>
            <ul>
              <li><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noopener">Interactive API Docs (OpenAPI)</a></li>
              <li><a href="http://127.0.0.1:8000/health" target="_blank" rel="noopener">System Health Check</a></li>
              <li><span class="text-subtle">OWASP Top 10 Aligned</span></li>
              <li><span class="text-subtle">DevSecOps Foundation</span></li>
            </ul>
          </div>
        </div>

        <div class="footer-bottom">
          <p>© 2026 EduVerse LMS. Built locally with Google Antigravity & modern web engineering standards.</p>
        </div>
      </div>
    </footer>
  `,
  styles: [`
    .footer {
      background: #0f172a;
      color: #94a3b8;
      border-top: 1px solid rgba(221, 214, 254, 0.2);
      margin-top: auto;
      padding: 3rem 0 1.5rem 0;
    }
    .footer-container {
      max-width: 1300px;
      margin: 0 auto;
      padding: 0 1.75rem;
    }
    .footer-top {
      display: grid;
      grid-template-columns: 2fr 1fr 1fr;
      gap: 3rem;
      margin-bottom: 2.5rem;
    }
    @media (max-width: 768px) {
      .footer-top {
        grid-template-columns: 1fr;
        gap: 2rem;
      }
    }
    .brand-col .brand-name {
      font-size: 1.5rem;
      font-weight: 800;
      color: #ffffff;
    }
    .brand-col .brand-accent {
      color: #a5b4fc;
    }
    .brand-desc {
      margin-top: 0.75rem;
      font-size: 0.9rem;
      line-height: 1.6;
      max-width: 380px;
      color: #94a3b8;
    }
    .tech-stack-badges {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: 1rem;
    }
    .pill {
      font-size: 0.75rem;
      padding: 0.25rem 0.75rem;
      border-radius: var(--radius-full);
      background-color: rgba(99, 102, 241, 0.15);
      border: 1px solid rgba(165, 180, 252, 0.25);
      color: #c7d2fe;
      font-family: var(--font-mono);
      font-weight: 500;
    }
    .footer-col h4 {
      color: #ffffff;
      font-size: 1rem;
      font-weight: 700;
      margin-bottom: 1rem;
    }
    .footer-col ul {
      list-style: none;
      padding: 0;
    }
    .footer-col li {
      margin-bottom: 0.6rem;
      font-size: 0.9rem;
    }
    .footer-col a {
      color: #94a3b8;
      transition: var(--transition);
    }
    .footer-col a:hover {
      color: #c7d2fe;
    }
    .text-subtle {
      color: #64748b;
    }
    .footer-bottom {
      border-top: 1px solid rgba(255, 255, 255, 0.08);
      padding-top: 1.5rem;
      text-align: center;
      font-size: 0.85rem;
      color: #64748b;
    }
  `]
})
export class FooterComponent {}
