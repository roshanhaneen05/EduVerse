import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink],
  template: `
    <div class="home-page">
      <header class="site-header">
        <div class="header-inner">
          <a class="brand" routerLink="/" aria-label="EduVerse home">
            <span class="brand-icon" aria-hidden="true">
              <svg viewBox="0 0 32 32" fill="none">
                <path d="M16 4 2 11l14 7 14-7-14-7Z" fill="currentColor"/>
                <path d="M6 14.5V21c0 3.5 4.5 6.5 10 6.5s10-3 10-6.5v-6.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
              </svg>
            </span>
            <span>Edu<span class="brand-accent">Verse</span></span>
          </a>

          <nav class="main-nav" aria-label="Main navigation">
            <a href="#home" class="nav-link active">Home</a>
            <a href="#about" class="nav-link">About</a>
            <a href="#courses" class="nav-link">Courses</a>
            <a href="#features" class="nav-link">Features</a>
            <a href="#contact" class="nav-link">Contact</a>
          </nav>

          <div class="header-actions">
            <a class="login-button" routerLink="/login">Login <span aria-hidden="true">→</span></a>
            <a class="register-button" routerLink="/register">Register</a>
          </div>
        </div>
      </header>

      <main>
        <section class="hero" id="home">
          <div class="hero-inner">
            <div class="hero-copy">
              <div class="hero-badge"><span></span> YOUR NEXT CHAPTER STARTS HERE</div>
              <h1>A Smarter Way to <span>Learn &amp; Grow.</span></h1>
              <p class="hero-description">
                Discover practical courses, learn at your own pace, and turn your curiosity into skills
                that move you forward.
              </p>
              <div class="hero-actions">
                <a class="button button-primary" routerLink="/login">
                  Get Started
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </a>
                <a class="button button-quiet" href="#courses">Explore courses</a>
              </div>
              <div class="hero-proof">
                <div class="proof-avatars" aria-hidden="true">
                  <span>S</span><span>M</span><span>A</span><span>+</span>
                </div>
                <div><strong>Learn something new today</strong><small>One lesson at a time, at your pace.</small></div>
              </div>
            </div>

            <div class="hero-visual">
              <div class="visual-glow"></div>
              <div class="visual-orbit orbit-one"></div>
              <div class="visual-orbit orbit-two"></div>
              <img src="/assets/images/learning-hero-illustration.png" alt="A welcoming study space with books and a laptop" class="hero-illustration"/>
              <div class="floating-note note-progress">
                <span class="note-icon progress-icon">✓</span>
                <span><strong>Keep progressing</strong><small>Your next lesson is waiting</small></span>
              </div>
              <div class="floating-note note-learning">
                <span class="note-icon book-icon">✦</span>
                <span><strong>Learn your way</strong><small>Lessons made for real life</small></span>
              </div>
              <div class="visual-caption"><span class="caption-dot"></span> A space to learn, build, and grow</div>
            </div>
          </div>
          <div class="hero-bottom-shape" aria-hidden="true"></div>
        </section>

        <section class="trust-strip" aria-label="EduVerse learning benefits">
          <div class="trust-inner">
            <span><b>01</b> Practical, structured courses</span>
            <span><b>02</b> Progress that keeps you motivated</span>
            <span><b>03</b> Guidance when you need it</span>
          </div>
        </section>

        <section class="about-section section-wrap" id="about">
          <div class="about-visual">
            <div class="about-image-frame">
              <img src="/assets/images/desk-laptop-illustration.png" alt="A laptop and books ready for a focused learning session"/>
              <div class="about-sticker"><span>Learn</span><b>with purpose.</b></div>
            </div>
            <div class="about-decoration decoration-a"></div>
            <div class="about-decoration decoration-b"></div>
          </div>
          <div class="about-copy">
            <span class="section-kicker">ABOUT EDUVERSE</span>
            <h2>Make room for what you can become.</h2>
            <p>
              EduVerse brings learning and teaching together in one thoughtful space. Explore clear,
              structured lessons, practice what you learn, and see your progress take shape.
            </p>
            <p>
              Whether you are beginning a new journey or sharing your expertise, the tools you need
              are right here.
            </p>
            <a class="text-link" routerLink="/login">Find your place at EduVerse <span aria-hidden="true">→</span></a>
          </div>
        </section>

        <section class="courses-section" id="courses">
          <div class="section-wrap">
            <div class="section-heading">
              <div>
                <span class="section-kicker">EXPLORE &amp; DISCOVER</span>
                <h2>Popular courses</h2>
                <p>Start with a subject that sparks your curiosity.</p>
              </div>
              <a routerLink="/login" class="text-link">Explore EduVerse <span aria-hidden="true">→</span></a>
            </div>

            <div class="course-grid">
              @for (course of courses; track course.title) {
                <article class="course-card">
                  <div class="course-art" [class]="course.theme">
                    @if (course.theme === 'python') {
                      <span class="course-symbol">Py</span>
                    } @else if (course.theme === 'web') {
                      <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><rect x="9" y="12" width="46" height="36" rx="6" stroke="currentColor" stroke-width="3"/><path d="M9 22h46M18 17h1m7 0h1m7 0h1M24 33l-6 5 6 5m16-10 6 5-6 5m-6-9-5 9" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    } @else if (course.theme === 'cloud') {
                      <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><path d="M17 46h31a11 11 0 0 0 1-22 17 17 0 0 0-33-2 12 12 0 0 0 1 24Z" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><path d="M24 36h16m-12-6-5 6 5 6m14-12 5 6-5 6" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    } @else {
                      <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><circle cx="32" cy="32" r="20" stroke="currentColor" stroke-width="3"/><circle cx="23" cy="25" r="3" fill="currentColor"/><circle cx="41" cy="25" r="3" fill="currentColor"/><circle cx="32" cy="39" r="3" fill="currentColor"/><path d="m25 27 5 9m9-9-5 9m-6-11h8m-8 14h8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
                    }
                    <span class="art-label">{{ course.category }}</span>
                  </div>
                  <div class="course-info">
                    <div class="course-meta"><span>{{ course.level }}</span><span class="meta-dot"></span><span>{{ course.lessons }} lessons</span></div>
                    <h3>{{ course.title }}</h3>
                    <p>{{ course.description }}</p>
                    <a routerLink="/login" class="course-link">View learning paths <span aria-hidden="true">→</span></a>
                  </div>
                </article>
              }
            </div>
          </div>
        </section>

        <section class="features-section section-wrap" id="features">
          <div class="section-heading centered">
            <span class="section-kicker">THE EDUVERSE EXPERIENCE</span>
            <h2>Everything you need to move forward</h2>
            <p>Supportive tools for meaningful learning, from your first lesson to your next big idea.</p>
          </div>
          <div class="feature-grid">
            <article class="feature-card">
              <div class="feature-icon icon-purple">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 9.5 9.5 3 12l6.5 2.5L12 21l2.5-6.5L21 12l-6.5-2.5L12 3Z"/></svg>
              </div>
              <h3>Learning that feels clear</h3>
              <p>Follow organized courses and focused lessons that make complex topics easier to approach.</p>
            </article>
            <article class="feature-card">
              <div class="feature-icon icon-blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19V5m0 14h17M8 15l4-4 3 2 5-6"/></svg>
              </div>
              <h3>Progress you can see</h3>
              <p>Keep track of lessons, activities, and achievements as you build momentum at your pace.</p>
            </article>
            <article class="feature-card">
              <div class="feature-icon icon-green">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 4 6v5c0 5 3.4 8.5 8 10 4.6-1.5 8-5 8-10V6l-8-3Z"/><path d="m9 12 2 2 4-4"/></svg>
              </div>
              <h3>Practice with purpose</h3>
              <p>Apply your new knowledge with quizzes and assignments designed to reinforce learning.</p>
            </article>
            <article class="feature-card">
              <div class="feature-icon icon-amber">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8 10h8m-8 4h5m-1 7-4-4H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2h-5l-4 4Z"/></svg>
              </div>
              <h3>Learning, together</h3>
              <p>Connect with instructors and classmates through conversations, guidance, and shared ideas.</p>
            </article>
          </div>
        </section>

        <section class="why-section">
          <div class="why-inner">
            <div class="why-copy">
              <span class="section-kicker">WHY CHOOSE EDUVERSE</span>
              <h2>A better learning experience, built around you.</h2>
              <p>Less friction between where you are and where you want to go. EduVerse brings your learning journey into focus.</p>
              <ul>
                <li><span>✓</span> Learn on your schedule, from any device</li>
                <li><span>✓</span> Keep courses and progress in one place</li>
                <li><span>✓</span> Get guidance from educators and learning tools</li>
              </ul>
              <a routerLink="/login" class="button button-primary">Get started today <span aria-hidden="true">→</span></a>
            </div>
            <div class="why-art">
              <div class="why-orb orb-large"></div>
              <div class="why-orb orb-small"></div>
              <img src="/assets/images/learning-hero-illustration.png" alt="Illustration of books and digital learning tools"/>
              <div class="why-stats"><strong>Every step</strong><span>takes you further.</span></div>
            </div>
          </div>
        </section>

        <section class="contact-cta" id="contact">
          <div class="cta-orb orb-left" aria-hidden="true"></div>
          <div class="cta-orb orb-right" aria-hidden="true"></div>
          <div class="cta-content">
            <span class="cta-kicker">YOUR JOURNEY STARTS HERE</span>
            <h2>Ready to learn something new?</h2>
            <p>Choose your path and take the first step with EduVerse.</p>
            <a routerLink="/login" class="button button-white">Get Started <span aria-hidden="true">→</span></a>
          </div>
        </section>
      </main>

      <footer class="home-footer">
        <div class="footer-main">
          <div class="footer-brand-col">
            <a class="brand footer-brand" routerLink="/">
              <span class="brand-icon" aria-hidden="true">
                <svg viewBox="0 0 32 32" fill="none"><path d="M16 4 2 11l14 7 14-7-14-7Z" fill="currentColor"/><path d="M6 14.5V21c0 3.5 4.5 6.5 10 6.5s10-3 10-6.5v-6.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/></svg>
              </span>
              <span>Edu<span class="brand-accent">Verse</span></span>
            </a>
            <p>A welcoming place to learn, teach, and keep growing.</p>
          </div>
          <div class="footer-links">
            <h3>Explore</h3>
            <a href="#about">About</a>
            <a href="#courses">Courses</a>
            <a href="#features">Features</a>
          </div>
          <div class="footer-links">
            <h3>Get started</h3>
            <a routerLink="/login">Sign in</a>
            <a routerLink="/register">Create an account</a>
          </div>
          <div class="footer-links">
            <h3>Contact</h3>
            <a href="mailto:support&#64;eduverse.io">support&#64;eduverse.io</a>
            <a href="#contact">We’re here to help</a>
          </div>
        </div>
        <div class="footer-bottom">
          <span>© 2026 EduVerse. All rights reserved.</span>
          <span>Thoughtful learning for a brighter future.</span>
        </div>
      </footer>
    </div>
  `,
  styles: [`
    :host { display: block; color: #191638; }
    .home-page { overflow: hidden; background: #fff; }
    .site-header { position: relative; z-index: 3; background: rgba(255,255,255,.92); border-bottom: 1px solid #f0eef8; }
    .header-inner { width: min(1200px, calc(100% - 3rem)); height: 82px; margin: auto; display: flex; align-items: center; justify-content: space-between; gap: 2rem; }
    .brand { display: inline-flex; align-items: center; gap: .55rem; color: #201c4d; font-size: 1.42rem; font-weight: 850; letter-spacing: -.055em; white-space: nowrap; }
    .brand-icon { display: inline-flex; width: 35px; height: 35px; color: #594ed2; }
    .brand-icon svg { width: 100%; height: 100%; }
    .brand-accent { color: #665bd8; }
    .main-nav { display: flex; align-items: center; gap: clamp(1.1rem, 2.5vw, 2.3rem); }
    .nav-link { position: relative; padding: .55rem 0; color: #5e6275; font-size: .88rem; font-weight: 650; }
    .nav-link:hover, .nav-link.active { color: #5549cb; }
    .nav-link.active::after { position: absolute; right: 0; bottom: 0; left: 0; height: 2px; content: ''; background: #665bd8; border-radius: 2px; }
    .login-button { display: inline-flex; align-items: center; gap: .6rem; padding: .68rem 1.12rem; border: 1px solid #dedaf7; border-radius: 10px; color: #5146c6; font-size: .86rem; font-weight: 750; transition: .2s ease; }
    .login-button:hover { color: #fff; background: #584ed0; border-color: #584ed0; box-shadow: 0 7px 18px rgba(88,78,208,.2); }
    .header-actions { display: flex; align-items: center; gap: .65rem; flex-shrink: 0; }
    .register-button { display: inline-flex; align-items: center; justify-content: center; padding: .68rem 1.12rem; border: 1px solid #584ed0; border-radius: 10px; color: #fff; background: #584ed0; font-size: .86rem; font-weight: 750; box-shadow: 0 5px 14px rgba(88,78,208,.16); transition: transform .2s ease, box-shadow .2s ease, background .2s ease; }
    .register-button:hover { color: #fff; background: #473dbb; box-shadow: 0 8px 19px rgba(88,78,208,.25); transform: translateY(-1px); }

    .hero { position: relative; isolation: isolate; overflow: hidden; background: linear-gradient(112deg, #fbfaff 0%, #f7f5ff 50%, #f0edff 100%); }
    .hero-inner { position: relative; z-index: 1; width: min(1200px, calc(100% - 3rem)); min-height: 570px; margin: auto; display: grid; grid-template-columns: 1fr 1fr; align-items: center; gap: 2rem; padding: 3.5rem 0 4.25rem; }
    .hero-copy { max-width: 555px; animation: enter-left .65s both; }
    .hero-badge { display: inline-flex; align-items: center; gap: .55rem; padding: .48rem .78rem; border: 1px solid #e5e0ff; border-radius: 999px; background: #fff; color: #5a50bf; font-size: .67rem; font-weight: 800; letter-spacing: .1em; }
    .hero-badge > span { width: 7px; height: 7px; border-radius: 50%; background: #756ae5; box-shadow: 0 0 0 4px #eeecff; }
    .hero h1 { margin: 1.4rem 0 1rem; max-width: 590px; font-size: clamp(2.85rem, 5.3vw, 4.4rem); line-height: 1.08; letter-spacing: -.065em; font-weight: 850; }
    .hero h1 span { color: #6558d8; }
    .hero-description { max-width: 500px; color: #697087; font-size: 1.05rem; line-height: 1.8; }
    .hero-actions { display: flex; gap: .85rem; flex-wrap: wrap; margin-top: 1.8rem; }
    .button { min-height: 48px; display: inline-flex; justify-content: center; align-items: center; gap: .75rem; padding: .8rem 1.22rem; border-radius: 11px; font-size: .9rem; font-weight: 750; transition: transform .2s ease, box-shadow .2s ease, background .2s ease; }
    .button:hover { transform: translateY(-2px); }
    .button svg { width: 18px; height: 18px; }
    .button-primary { color: #fff; background: linear-gradient(135deg, #685ce0, #5247c8); box-shadow: 0 10px 24px rgba(89,78,208,.23); }
    .button-primary:hover { color: #fff; box-shadow: 0 14px 28px rgba(89,78,208,.3); }
    .button-quiet { color: #56528a; background: rgba(255,255,255,.75); border: 1px solid #e5e1f4; }
    .button-quiet:hover { color: #5146c6; background: #fff; }
    .hero-proof { display: flex; align-items: center; gap: .8rem; margin-top: 2.1rem; }
    .proof-avatars { display: flex; padding-left: 4px; }
    .proof-avatars span { width: 29px; height: 29px; display: grid; place-items: center; margin-left: -4px; border: 2px solid #fbfaff; border-radius: 50%; color: #fff; background: #8d7ce2; font-size: .62rem; font-weight: 800; }
    .proof-avatars span:nth-child(2) { background: #c28b9b; }.proof-avatars span:nth-child(3) { background: #729b9b; }.proof-avatars span:nth-child(4) { color: #574cc4; background: #e6e2ff; }
    .hero-proof strong, .hero-proof small { display: block; }.hero-proof strong { color: #42435d; font-size: .75rem; }.hero-proof small { color: #8a8ca0; font-size: .7rem; margin-top: .08rem; }
    .hero-visual { position: relative; min-height: 440px; display: grid; place-items: center; animation: enter-right .75s both; }
    .visual-glow { position: absolute; width: 75%; aspect-ratio: 1; border-radius: 50%; background: radial-gradient(circle, rgba(184,174,255,.5), rgba(221,216,255,.2) 53%, transparent 72%); }
    .visual-orbit { position: absolute; border: 1px solid rgba(133,121,220,.2); border-radius: 50%; }
    .orbit-one { width: 88%; height: 76%; transform: rotate(-17deg); }.orbit-two { width: 76%; height: 90%; transform: rotate(25deg); }
    .hero-illustration { position: relative; z-index: 1; width: min(92%, 475px); max-height: 380px; object-fit: contain; border-radius: 28px; filter: drop-shadow(0 25px 35px rgba(58,46,132,.15)); animation: float 5s ease-in-out infinite; }
    .floating-note { position: absolute; z-index: 2; display: flex; align-items: center; gap: .65rem; padding: .75rem .9rem; border: 1px solid rgba(232,229,248,.9); border-radius: 13px; background: rgba(255,255,255,.94); box-shadow: 0 12px 30px rgba(53,45,115,.1); animation: float 5s ease-in-out infinite; }
    .note-progress { top: 16%; right: -1%; }.note-learning { bottom: 14%; left: 0; animation-delay: -2.5s; }
    .note-icon { width: 31px; height: 31px; display: grid; place-items: center; border-radius: 9px; font-weight: 850; }
    .progress-icon { color: #29876d; background: #e2f5ee; }.book-icon { color: #6558d8; background: #eeebff; }
    .floating-note strong, .floating-note small { display: block; white-space: nowrap; }.floating-note strong { color: #35334f; font-size: .68rem; }.floating-note small { margin-top: .16rem; color: #88899d; font-size: .59rem; }
    .visual-caption { position: absolute; right: 0; bottom: 1%; display: flex; align-items: center; gap: .45rem; color: #86839f; font-size: .67rem; font-weight: 650; }
    .caption-dot { width: 6px; height: 6px; border-radius: 50%; background: #8b81e6; }
    .hero-bottom-shape { position: absolute; right: -5%; bottom: -120px; left: -5%; height: 170px; background: #fff; border-radius: 50% 50% 0 0 / 45% 45% 0 0; }
    .trust-strip { position: relative; z-index: 1; background: #fff; }
    .trust-inner { width: min(1100px, calc(100% - 3rem)); min-height: 95px; margin: auto; display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; border-bottom: 1px solid #f0eef7; }
    .trust-inner span { color: #74778b; font-size: .77rem; font-weight: 650; }.trust-inner b { margin-right: .4rem; color: #8278dd; font-size: .69rem; letter-spacing: .08em; }
    .section-wrap { width: min(1120px, calc(100% - 3rem)); margin: auto; }
    .about-section { display: grid; grid-template-columns: .95fr 1fr; align-items: center; gap: clamp(3rem, 8vw, 7rem); padding-top: 7rem; padding-bottom: 7rem; }
    .about-visual { position: relative; padding: 1.3rem 1.1rem 1rem 0; }
    .about-image-frame { position: relative; z-index: 1; overflow: hidden; min-height: 325px; display: grid; place-items: center; border: 10px solid #fff; border-radius: 26px; background: linear-gradient(145deg, #f1eeff, #fbfaff); box-shadow: 0 22px 50px rgba(54,47,114,.11); }
    .about-image-frame img { width: 100%; max-height: 330px; object-fit: contain; }
    .about-sticker { position: absolute; right: -1rem; bottom: 1rem; padding: .75rem 1rem; border: 1px solid #e8e4f8; border-radius: 13px; background: #fff; box-shadow: 0 12px 28px rgba(56,47,122,.1); transform: rotate(2deg); }
    .about-sticker span, .about-sticker b { display: block; }.about-sticker span { color: #8988a0; font-size: .65rem; }.about-sticker b { color: #5449c8; font-size: .84rem; }
    .about-decoration { position: absolute; border-radius: 50%; }.decoration-a { top: -1rem; left: -1.5rem; width: 86px; height: 86px; background: #f0edff; }.decoration-b { right: 5%; bottom: -1rem; width: 52px; height: 52px; border: 10px solid #eeeaff; }
    .section-kicker { display: inline-block; color: #665bd1; font-size: .68rem; font-weight: 850; letter-spacing: .15em; }
    .about-copy h2, .section-heading h2, .why-copy h2 { margin: .7rem 0 .85rem; color: #211d48; font-size: clamp(1.85rem, 3.2vw, 2.6rem); font-weight: 800; line-height: 1.2; letter-spacing: -.045em; }
    .about-copy p { margin: 0 0 1rem; color: #70758a; font-size: .93rem; line-height: 1.85; }
    .text-link { display: inline-flex; align-items: center; gap: .55rem; margin-top: .45rem; color: #584dca; font-size: .83rem; font-weight: 750; }.text-link:hover { gap: .8rem; color: #3e34a9; }
    .courses-section { padding: 6.2rem 0; background: #f8f7fd; }
    .section-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 2rem; margin-bottom: 2.2rem; }
    .section-heading h2 { margin-bottom: .45rem; }.section-heading p { color: #777b90; font-size: .9rem; }.section-heading > .text-link { white-space: nowrap; margin-bottom: .35rem; }
    .course-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; }
    .course-card { overflow: hidden; border: 1px solid #eceaf5; border-radius: 17px; background: #fff; box-shadow: 0 10px 28px rgba(50,44,106,.045); transition: transform .22s ease, box-shadow .22s ease; }
    .course-card:hover { transform: translateY(-5px); box-shadow: 0 18px 36px rgba(50,44,106,.1); }
    .course-art { position: relative; height: 145px; display: grid; place-items: center; color: #665bd8; background: #f0edff; }
    .course-art svg { width: 63px; height: 63px; }.course-art.python { color: #5253bd; background: linear-gradient(135deg, #e8e9ff, #f1efff); }.course-art.web { color: #b26d37; background: linear-gradient(135deg, #fff1e2, #fff7ec); }.course-art.cloud { color: #4589ac; background: linear-gradient(135deg, #e6f4fb, #eff9fc); }.course-art.ai { color: #6f58bb; background: linear-gradient(135deg, #eee8ff, #f8f2ff); }
    .course-symbol { font-size: 2.8rem; font-weight: 850; letter-spacing: -.08em; }
    .art-label { position: absolute; right: .75rem; bottom: .7rem; padding: .32rem .55rem; border: 1px solid rgba(255,255,255,.8); border-radius: 999px; background: rgba(255,255,255,.7); color: #5f5a7b; font-size: .58rem; font-weight: 750; }
    .course-info { padding: 1.05rem 1.05rem 1.15rem; }.course-meta { display: flex; align-items: center; gap: .4rem; color: #85879b; font-size: .64rem; font-weight: 650; }.meta-dot { width: 3px; height: 3px; border-radius: 50%; background: #aaa7bb; }
    .course-info h3 { min-height: 2.7rem; margin: .65rem 0 .45rem; color: #2b2849; font-size: .97rem; line-height: 1.4; letter-spacing: -.02em; }
    .course-info p { min-height: 4rem; color: #7b7f91; font-size: .72rem; line-height: 1.65; }
    .course-link { display: inline-flex; gap: .45rem; color: #5d52cb; font-size: .71rem; font-weight: 750; }.course-link:hover { gap: .7rem; }
    .features-section { padding-top: 6.5rem; padding-bottom: 6.5rem; }
    .section-heading.centered { display: block; max-width: 650px; margin: 0 auto 2.5rem; text-align: center; }.centered h2 { font-size: clamp(1.85rem, 3vw, 2.5rem); }.centered p { max-width: 560px; margin: auto; line-height: 1.75; }
    .feature-grid { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 1rem; }
    .feature-card { padding: 1.35rem; border: 1px solid #efedf7; border-radius: 16px; background: #fff; transition: transform .2s ease, box-shadow .2s ease; }.feature-card:hover { transform: translateY(-4px); box-shadow: 0 14px 32px rgba(50,44,106,.08); }
    .feature-icon { width: 45px; height: 45px; display: grid; place-items: center; margin-bottom: 1.1rem; border-radius: 13px; }.feature-icon svg { width: 23px; height: 23px; }
    .icon-purple { color: #6557d3; background: #f0edff; }.icon-blue { color: #4a86bf; background: #eaf5ff; }.icon-green { color: #488c78; background: #e8f6f0; }.icon-amber { color: #b17a39; background: #fff4e3; }
    .feature-card h3 { margin-bottom: .5rem; color: #302d4e; font-size: .91rem; }.feature-card p { color: #7b7f91; font-size: .75rem; line-height: 1.7; }
    .why-section { overflow: hidden; background: linear-gradient(115deg, #f6f4ff 0%, #f1efff 56%, #eeebff 100%); }
    .why-inner { width: min(1120px, calc(100% - 3rem)); min-height: 450px; margin: auto; display: grid; grid-template-columns: 1.05fr .95fr; align-items: center; gap: 3rem; padding: 4.5rem 0; }
    .why-copy { max-width: 540px; }.why-copy h2 { font-size: clamp(1.9rem, 3.3vw, 2.65rem); }.why-copy > p { max-width: 470px; color: #70758a; font-size: .9rem; line-height: 1.8; }
    .why-copy ul { display: grid; gap: .9rem; margin: 1.4rem 0 1.8rem; padding: 0; list-style: none; }.why-copy li { display: flex; align-items: center; gap: .65rem; color: #575c74; font-size: .8rem; font-weight: 650; }.why-copy li span { width: 21px; height: 21px; display: grid; place-items: center; border-radius: 50%; color: #4f9a7f; background: #e2f5ec; font-size: .7rem; }
    .why-art { position: relative; min-height: 340px; display: grid; place-items: center; }.why-art img { position: relative; z-index: 1; width: 95%; max-height: 330px; object-fit: contain; filter: drop-shadow(0 22px 25px rgba(57,47,139,.14)); }
    .why-orb { position: absolute; border-radius: 50%; }.orb-large { width: 310px; height: 310px; background: linear-gradient(145deg, #e4dfff, #f6f4ff); }.orb-small { right: 8%; bottom: 10%; width: 75px; height: 75px; border: 13px solid #dfdafc; }
    .why-stats { position: absolute; z-index: 2; right: 0; bottom: 5%; display: flex; flex-direction: column; padding: .8rem 1rem; border: 1px solid #ebe8fa; border-radius: 13px; background: #fff; box-shadow: 0 12px 28px rgba(56,47,122,.1); }.why-stats strong { color: #5147c3; font-size: .77rem; }.why-stats span { color: #89899b; font-size: .65rem; }
    .contact-cta { position: relative; overflow: hidden; margin: 5rem auto; width: min(1120px, calc(100% - 3rem)); min-height: 270px; display: grid; place-items: center; border-radius: 24px; color: #fff; background: linear-gradient(115deg, #5248c5 0%, #6c5ed5 55%, #8071e1 100%); }
    .cta-content { position: relative; z-index: 1; padding: 3rem 1.5rem; text-align: center; }.cta-kicker { color: #dedbff; font-size: .65rem; font-weight: 850; letter-spacing: .15em; }.cta-content h2 { margin: .65rem 0 .5rem; color: #fff; font-size: clamp(1.75rem, 3.5vw, 2.6rem); letter-spacing: -.045em; }.cta-content p { margin-bottom: 1.35rem; color: #e5e1ff; font-size: .86rem; }
    .button-white { min-height: 43px; padding: .67rem 1rem; color: #554ac5; background: #fff; font-size: .78rem; }.button-white:hover { color: #4137ad; background: #f5f3ff; }
    .cta-orb { position: absolute; border: 1px solid rgba(255,255,255,.17); border-radius: 50%; }.orb-left { top: -80px; left: -40px; width: 260px; height: 260px; box-shadow: 0 0 0 28px rgba(255,255,255,.035), 0 0 0 58px rgba(255,255,255,.025); }.orb-right { right: -70px; bottom: -130px; width: 330px; height: 330px; box-shadow: 0 0 0 30px rgba(255,255,255,.035); }
    .home-footer { padding: 3.2rem max(1.5rem, calc((100% - 1120px) / 2)) 1.2rem; color: #aaaabe; background: #201e3c; }
    .footer-main { display: grid; grid-template-columns: 1.5fr repeat(3, 1fr); gap: 2.5rem; padding-bottom: 2.5rem; }.footer-brand { color: #fff; }.footer-brand .brand-accent { color: #aaa2ff; }.footer-brand-col p { max-width: 250px; margin-top: .85rem; color: #aaaabe; font-size: .74rem; line-height: 1.75; }
    .footer-links { display: flex; flex-direction: column; align-items: flex-start; gap: .55rem; }.footer-links h3 { margin: .3rem 0 .4rem; color: #fff; font-size: .78rem; }.footer-links a { color: #aaaabe; font-size: .71rem; }.footer-links a:hover { color: #d3ceff; }
    .footer-bottom { display: flex; justify-content: space-between; gap: 1rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,.1); color: #8e8da5; font-size: .65rem; }
    @keyframes float { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
    @keyframes enter-left { from { opacity: 0; transform: translateX(-16px); } to { opacity: 1; transform: translateX(0); } }
    @keyframes enter-right { from { opacity: 0; transform: translateX(16px); } to { opacity: 1; transform: translateX(0); } }
    @media (max-width: 960px) {
      .hero-inner { min-height: 510px; }.hero-visual { min-height: 370px; }.floating-note { padding: .6rem; }.note-progress { right: -2%; }
      .course-grid, .feature-grid { grid-template-columns: repeat(2, minmax(0,1fr)); }.footer-main { gap: 1.5rem; }
    }
    @media (max-width: 700px) {
      .header-inner { width: calc(100% - 2rem); height: 70px; gap: .75rem; }.main-nav { display: none; }.brand { font-size: 1.25rem; }.brand-icon { width: 31px; height: 31px; }
      .hero-inner { width: calc(100% - 2.5rem); grid-template-columns: 1fr; gap: .5rem; padding: 3.4rem 0 4.7rem; }.hero-copy { max-width: none; }.hero h1 { max-width: 520px; font-size: clamp(2.55rem, 10vw, 3.65rem); }.hero-description { max-width: 540px; font-size: .94rem; }
      .hero-visual { width: min(100%, 500px); min-height: 330px; margin: auto; }.hero-illustration { max-height: 300px; }.note-progress { top: 10%; right: 0; }.note-learning { bottom: 10%; left: 0; }.visual-caption { right: 2%; }
      .trust-inner { width: calc(100% - 2rem); min-height: 0; align-items: flex-start; flex-direction: column; gap: .85rem; padding: 1.25rem 0; }
      .section-wrap, .why-inner { width: calc(100% - 2.5rem); }.about-section { grid-template-columns: 1fr; gap: 2rem; padding-top: 4.5rem; padding-bottom: 4.5rem; }.about-visual { max-width: 470px; margin: auto; }.about-image-frame { min-height: 270px; }
      .courses-section { padding: 4.5rem 0; }.section-heading { align-items: flex-start; flex-direction: column; gap: .75rem; }.section-heading > .text-link { margin: 0; }.features-section { padding-top: 4.5rem; padding-bottom: 4.5rem; }.section-heading.centered { align-items: center; }
      .why-inner { grid-template-columns: 1fr; gap: 1rem; padding: 4rem 0 2.8rem; }.why-art { min-height: 280px; }.why-art img { max-height: 280px; }.orb-large { width: 250px; height: 250px; }
      .contact-cta { width: calc(100% - 2rem); margin: 3.5rem auto; min-height: 240px; }.footer-main { grid-template-columns: repeat(2, minmax(0,1fr)); }.footer-brand-col { grid-column: 1 / -1; }
    }
    @media (max-width: 430px) {
      .login-button, .register-button { padding: .58rem .72rem; font-size: .76rem; }.header-actions { gap: .4rem; }.hero-inner { width: calc(100% - 2rem); }.hero-proof { margin-top: 1.6rem; }.hero-visual { min-height: 280px; }.hero-illustration { max-height: 255px; }
      .floating-note { gap: .4rem; padding: .5rem; }.note-icon { width: 26px; height: 26px; }.floating-note strong { font-size: .6rem; }.floating-note small { font-size: .53rem; }.visual-caption { font-size: .58rem; }
      .course-grid, .feature-grid { grid-template-columns: 1fr; }.course-art { height: 160px; }.course-info h3, .course-info p { min-height: auto; }.feature-card { padding: 1.2rem; }.footer-main { gap: 1.5rem 1rem; }.footer-bottom { flex-direction: column; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important; transition-duration: .01ms !important; }
    }
  `]
})
export class LandingComponent {
  readonly courses = [
    { title: 'Python Programming', category: 'Programming', level: 'Beginner', lessons: 24, theme: 'python', description: 'Build your foundation in Python with practical, hands-on lessons.' },
    { title: 'Web Development', category: 'Web', level: 'Beginner', lessons: 32, theme: 'web', description: 'Create responsive websites and understand the modern web.' },
    { title: 'Cloud Computing', category: 'Cloud', level: 'Intermediate', lessons: 20, theme: 'cloud', description: 'Learn the building blocks of reliable cloud applications.' },
    { title: 'Artificial Intelligence', category: 'AI & Data', level: 'Intermediate', lessons: 28, theme: 'ai', description: 'Explore machine learning, responsible AI, and model evaluation.' }
  ];
}
