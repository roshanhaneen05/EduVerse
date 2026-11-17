import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  InstructorDifficulty,
  InstructorPaperOutline,
  InstructorPaperQuestion,
  InstructorQuestionPaper,
  InstructorQuestionPaperSummary,
  InstructorQuestionType,
  InstructorTeachingCourse,
  QuestionPaperGeneratePayload,
} from '../../core/models/instructor-ai.model';
import { InstructorService } from '../../core/services/instructor.service';

@Component({
  selector: 'app-ai-question-paper-generator',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  template: `
    <main class="paper-page">
      <div class="container">
        <a routerLink="/instructor/dashboard" class="back-link">← Instructor Dashboard</a>
        <header class="page-header">
          <div>
            <span class="eyebrow">AI Teaching Tools</span>
            <h1>AI Question Paper Generator</h1>
            <p>Create a course-grounded draft, edit it, then publish or export the paper and answer key separately.</p>
          </div>
        </header>
        @if (message) { <div class="alert" [class.error]="isError">{{ message }}</div> }

        <section class="layout">
          <aside class="card saved">
            <h2>Saved papers</h2>
            <button type="button" class="btn outline full" (click)="newPaper()">+ New paper</button>
            @for (saved of savedPapers; track saved.id) {
              <div class="saved-row">
                <button type="button" class="saved-item" [class.active]="paper?.id === saved.id" (click)="openPaper(saved.id)">
                  <strong>{{ saved.title }}</strong>
                  <small>{{ saved.course_title }} · {{ saved.status | titlecase }}</small>
                  <small>{{ saved.total_marks }} marks · {{ saved.updated_at | date:'shortDate' }}</small>
                </button>
                <button type="button" class="btn tiny danger" (click)="deletePaper(saved.id)" [disabled]="busy" aria-label="Delete saved question paper">Delete</button>
              </div>
            } @empty { <p class="muted">No question papers saved.</p> }
          </aside>

          <div class="content">
            <section class="card configuration">
              <h2>Paper configuration</h2>
              <div class="form-grid">
                <label>Assigned course
                  <select [(ngModel)]="courseId" (ngModelChange)="selectCourse($event)">
                    <option [ngValue]="null">Select course</option>
                    @for (course of courses; track course.id) { <option [ngValue]="course.id">{{ course.title }}</option> }
                  </select>
                </label>
                <label>Paper title<input [(ngModel)]="title" maxlength="255" placeholder="Mid-term assessment" /></label>
                <label>Difficulty
                  <select [(ngModel)]="difficulty">
                    <option value="easy">Easy</option><option value="medium">Medium</option>
                    <option value="hard">Hard</option><option value="mixed">Mixed</option>
                  </select>
                </label>
                <label>Questions<input type="number" min="1" max="100" [(ngModel)]="questionCount" /></label>
                <label>Total marks<input type="number" min="1" step="0.5" [(ngModel)]="totalMarks" /></label>
                <label>Duration (minutes)<input type="number" min="1" max="600" [(ngModel)]="durationMinutes" /></label>
                <label>Optional exam date<input type="date" [(ngModel)]="examDate" /></label>
              </div>
              <div class="selection-grid">
                <div>
                  <h3>Modules</h3>
                  @if (!outline) { <p class="muted">Select a course to load its modules.</p> }
                  @for (section of outline?.sections ?? []; track section.id) {
                    <label class="check-row">
                      <input type="checkbox" [checked]="selectedSectionIds.includes(section.id)" (change)="toggleSection(section.id, $any($event.target).checked)" />
                      {{ section.title }}
                    </label>
                  }
                </div>
                <div>
                  <h3>Lessons</h3>
                  @for (section of selectedSections; track section.id) {
                    <strong class="lesson-group">{{ section.title }}</strong>
                    @for (lesson of section.lessons; track lesson.id) {
                      <label class="check-row">
                        <input type="checkbox" [checked]="selectedLessonIds.includes(lesson.id)" (change)="toggleLesson(lesson.id, $any($event.target).checked)" />
                        {{ lesson.title }}
                      </label>
                    }
                  }
                  @if (selectedSections.length === 0) { <p class="muted">Select a module to choose its lessons.</p> }
                </div>
              </div>
              <div class="types">
                <h3>Question types</h3>
                @for (type of questionTypeOptions; track type.value) {
                  <label class="check-row inline">
                    <input type="checkbox" [checked]="selectedTypes.includes(type.value)" (change)="toggleType(type.value, $any($event.target).checked)" />
                    {{ type.label }}
                  </label>
                }
              </div>
              <button class="btn primary" type="button" (click)="generate()" [disabled]="busy || !canGenerate">
                {{ busy ? 'Generating from lesson content…' : 'Generate paper with AI' }}
              </button>
            </section>

            @if (paper) {
              <section class="card editor">
                <div class="editor-header">
                  <div><h2>{{ paper.title }}</h2><p>{{ paper.course_title }} · {{ paper.duration_minutes }} min · {{ paper.status | titlecase }}</p></div>
                  <strong class="total">{{ questionMarks }} / {{ paper.total_marks }} marks</strong>
                </div>
                <div class="metadata-grid">
                  <label>Title<input [(ngModel)]="paper.title" /></label>
                  <label>Total marks<input type="number" min="1" step="0.5" [ngModel]="paper.total_marks" (ngModelChange)="setTotalMarks($event)" /></label>
                  <label>Duration<input type="number" min="1" [(ngModel)]="paper.duration_minutes" /></label>
                  <label>Difficulty
                    <select [(ngModel)]="paper.difficulty">
                      <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option><option value="mixed">Mixed</option>
                    </select>
                  </label>
                  <label>Exam date<input type="date" [(ngModel)]="paper.exam_date" /></label>
                </div>
                <div class="actions">
                  <button class="btn outline" type="button" (click)="previewMode = !previewMode">{{ previewMode ? 'Edit questions' : 'Preview question paper' }}</button>
                  <button class="btn outline" type="button" (click)="addQuestion()" [disabled]="previewMode">Add question</button>
                  <button class="btn primary" type="button" (click)="savePaper()" [disabled]="busy || questionMarks !== paper.total_marks">Save as draft</button>
                  <button class="btn publish" type="button" (click)="publishPaper()" [disabled]="busy || questionMarks !== paper.total_marks || paper.status === 'published'">Publish</button>
                  <button class="btn outline" type="button" (click)="downloadPdf(false)" [disabled]="busy">Export question paper PDF</button>
                  <button class="btn outline" type="button" (click)="downloadPdf(true)" [disabled]="busy">Export answer key PDF</button>
                </div>
                @if (questionMarks !== paper.total_marks) {
                  <p class="validation">Question marks currently total {{ questionMarks }}. Update marks or total before saving.</p>
                }
                @for (question of paper.questions; track question.id ?? question.question_order; let i = $index) {
                  <article class="question-card">
                    <div class="question-heading">
                      <h3>Question {{ i + 1 }}</h3>
                      @if (!previewMode) {
                        <div class="actions compact">
                          <button class="btn tiny outline" type="button" (click)="moveQuestion(i, -1)" [disabled]="i === 0">↑</button>
                          <button class="btn tiny outline" type="button" (click)="moveQuestion(i, 1)" [disabled]="i === paper.questions.length - 1">↓</button>
                          @if (question.id) { <button class="btn tiny outline" type="button" (click)="regenerateQuestion(question)" [disabled]="busy">Regenerate</button> }
                          <button class="btn tiny danger" type="button" (click)="deleteQuestion(i)">Delete</button>
                        </div>
                      }
                    </div>
                    @if (previewMode) {
                      <p class="preview-question">{{ question.question_text }} <strong>({{ question.marks }} marks)</strong></p>
                      @for (option of question.options; track $index; let o = $index) { <p class="option">({{ letter(o) }}) {{ option }}</p> }
                    } @else {
                      <label>Question text<textarea rows="3" [(ngModel)]="question.question_text"></textarea></label>
                      <div class="question-meta">
                        <label>Type
                          <select [(ngModel)]="question.question_type" (ngModelChange)="changeQuestionType(question)">
                            @for (type of questionTypeOptions; track type.value) { <option [value]="type.value">{{ type.label }}</option> }
                          </select>
                        </label>
                        <label>Difficulty
                          <select [(ngModel)]="question.difficulty">
                            <option value="easy">Easy</option><option value="medium">Medium</option><option value="hard">Hard</option>
                          </select>
                        </label>
                        <label>Marks<input type="number" min="0.1" step="0.1" [(ngModel)]="question.marks" (ngModelChange)="recalculateMarks()" /></label>
                      </div>
                      @if (question.question_type === 'mcq') {
                        <div class="option-editor">
                          @for (option of question.options; track $index; let o = $index) {
                            <label>Option {{ letter(o) }}<input [(ngModel)]="question.options[o]" /></label>
                          }
                          <label>Correct option
                            <select [(ngModel)]="question.correct_answer">
                              @for (option of question.options; track $index; let o = $index) { <option [value]="option">{{ letter(o) }}. {{ option }}</option> }
                            </select>
                          </label>
                        </div>
                      } @else if (question.question_type === 'true_false') {
                        <label>Correct answer<select [(ngModel)]="question.correct_answer"><option>True</option><option>False</option></select></label>
                      } @else {
                        <label>Expected answer<input [(ngModel)]="question.correct_answer" /></label>
                      }
                      <label>Explanation / marking guidelines<textarea rows="2" [(ngModel)]="question.explanation"></textarea></label>
                    }
                    @if (previewMode && !showAnswerKey) { <p class="answer-line">Answer: _________________________________________</p> }
                    @if (previewMode && showAnswerKey) { <p class="answer-key"><strong>Answer:</strong> {{ question.correct_answer }} <span>— {{ question.explanation }}</span></p> }
                  </article>
                }
                <button class="btn outline" type="button" (click)="showAnswerKey = !showAnswerKey">
                  {{ showAnswerKey ? 'Hide' : 'Preview' }} answer key
                </button>
              </section>
            }
          </div>
        </section>
      </div>
    </main>
  `,
  styles: [`
    .paper-page{min-height:100vh;padding:2rem 0 4rem;background:var(--bg-app,#faf7fb);color:var(--text-primary,#2c2430)}
    .back-link{display:inline-block;margin-bottom:1.25rem;color:var(--primary,#d9468f);font-weight:700}
    .eyebrow{color:#c02678;font-weight:800;text-transform:uppercase;letter-spacing:.08em;font-size:.75rem}
    h1{margin:.35rem 0;font-size:clamp(1.7rem,4vw,2.4rem)}h2{font-size:1.15rem;margin:0 0 .45rem}h3{font-size:.92rem;margin:.5rem 0}
    p{color:var(--text-muted,#756b79);line-height:1.5}.layout{display:grid;grid-template-columns:260px minmax(0,1fr);gap:1rem}
    .card{background:#fff;border:1px solid #eee4ed;border-radius:16px;padding:1.25rem;box-shadow:0 8px 26px #5b26420a;margin-bottom:1rem}
    label{display:grid;gap:.4rem;font-size:.82rem;font-weight:700;color:#574b5b}
    input,select,textarea{width:100%;padding:.68rem .75rem;border:1px solid #ded5df;border-radius:9px;background:#fff;color:#2c2430;font:inherit}
    textarea{resize:vertical;line-height:1.5}
    .saved{align-self:start;position:sticky;top:1rem}.saved-row{display:flex;align-items:center;gap:.35rem}.saved-item{width:100%;text-align:left;display:grid;gap:.25rem;padding:.75rem;margin:.45rem 0;border:1px solid #eee4ed;border-radius:10px;background:#fff;color:#392d3b;cursor:pointer}
    .saved-item.active{border-color:#d9468f;background:#fff7fb}.saved-item small,.muted{color:#827783;font-size:.78rem}
    .btn{border:0;border-radius:9px;padding:.68rem .9rem;font-weight:750;cursor:pointer}.btn:disabled{opacity:.5;cursor:not-allowed}
    .primary{background:#d9468f;color:#fff}.publish{background:#8c4ac4;color:#fff}.outline{background:#fff;border:1px solid #d9c8d7;color:#61425d}.danger{background:#fff0f2;color:#b42340}
    .full{width:100%}.form-grid,.metadata-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.8rem;margin:1rem 0}
    .selection-grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;border-top:1px solid #f0e9f0;padding-top:.8rem}.check-row{display:flex;align-items:center;gap:.55rem;margin:.45rem 0;font-weight:500}.check-row input{width:auto}
    .lesson-group{display:block;margin:.7rem 0 .3rem;color:#77456b}.types{border-top:1px solid #f0e9f0;padding:.6rem 0}.inline{display:inline-flex;margin:0 1rem .5rem 0}
    .actions{display:flex;flex-wrap:wrap;gap:.55rem;margin:1rem 0}.compact{margin:0}.tiny{padding:.35rem .55rem;font-size:.78rem}
    .editor-header,.question-heading{display:flex;justify-content:space-between;align-items:center;gap:1rem}.editor-header p{margin:.1rem 0}.total{color:#bd2777}
    .question-card{padding:1rem 0;border-top:1px solid #eee4ed}.question-meta,.option-editor{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.7rem;margin:.7rem 0}
    .preview-question{font-size:1rem;color:#322a34}.option{margin:.35rem 0 .35rem 1rem}.answer-line,.answer-key{margin-top:1rem;padding:.6rem;background:#fff9fc;border-radius:8px}.answer-key{color:#17693a}
    .validation{padding:.6rem;background:#fff0f2;color:#a21c3b;border-radius:8px}.alert{padding:.8rem 1rem;margin-bottom:1rem;background:#effaf2;color:#17693a;border-radius:10px}.alert.error{background:#fff0f2;color:#a21c3b}
    @media(max-width:850px){.layout{grid-template-columns:1fr}.saved{position:static}.selection-grid{grid-template-columns:1fr}}
    @media(max-width:500px){.card{padding:1rem}.editor-header{align-items:flex-start;flex-direction:column}.actions>*{flex:1}}
  `],
})
export class AIQuestionPaperGeneratorComponent implements OnInit {
  courses: InstructorTeachingCourse[] = [];
  savedPapers: InstructorQuestionPaperSummary[] = [];
  outline: InstructorPaperOutline | null = null;
  courseId: number | null = null;
  selectedSectionIds: number[] = [];
  selectedLessonIds: number[] = [];
  selectedTypes: InstructorQuestionType[] = ['mcq', 'short_answer'];
  title = '';
  difficulty: InstructorDifficulty | 'mixed' = 'mixed';
  questionCount = 10;
  totalMarks = 100;
  durationMinutes = 90;
  examDate = '';
  paper: InstructorQuestionPaper | null = null;
  previewMode = false;
  showAnswerKey = false;
  busy = false;
  message = '';
  isError = false;
  questionTypeOptions: Array<{ value: InstructorQuestionType; label: string }> = [
    { value: 'mcq', label: 'Multiple choice' },
    { value: 'true_false', label: 'True or false' },
    { value: 'short_answer', label: 'Short answer' },
    { value: 'long_answer', label: 'Long answer' },
    { value: 'fill_blank', label: 'Fill in the blanks' },
  ];

  constructor(private instructorService: InstructorService) {}

  ngOnInit(): void {
    this.instructorService.getTeachingCourses().subscribe({
      next: (items) => this.courses = items,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load assigned courses.'),
    });
    this.loadSavedPapers();
  }

  get selectedSections() {
    return (this.outline?.sections ?? []).filter((section) => this.selectedSectionIds.includes(section.id));
  }

  get questionMarks(): number {
    return Math.round((this.paper?.questions.reduce((sum, item) => sum + Number(item.marks || 0), 0) ?? 0) * 100) / 100;
  }

  get canGenerate(): boolean {
    return !!this.courseId && !!this.title.trim() && this.selectedSectionIds.length > 0
      && this.selectedLessonIds.length > 0 && this.selectedTypes.length > 0
      && this.questionCount >= 1 && this.totalMarks > 0 && this.durationMinutes >= 1;
  }

  selectCourse(courseId: number | null): void {
    this.courseId = courseId;
    this.selectedSectionIds = [];
    this.selectedLessonIds = [];
    this.outline = null;
    if (!courseId) return;
    this.instructorService.getTeachingCourseOutline(courseId).subscribe({
      next: (outline) => this.outline = outline,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load course modules and lessons.'),
    });
  }

  toggleSection(sectionId: number, checked: boolean): void {
    this.selectedSectionIds = checked
      ? [...this.selectedSectionIds, sectionId]
      : this.selectedSectionIds.filter((id) => id !== sectionId);
    const included = new Set(this.selectedSections.flatMap((section) => section.lessons.map((lesson) => lesson.id)));
    this.selectedLessonIds = this.selectedLessonIds.filter((id) => included.has(id));
  }

  toggleLesson(lessonId: number, checked: boolean): void {
    this.selectedLessonIds = checked
      ? [...this.selectedLessonIds, lessonId]
      : this.selectedLessonIds.filter((id) => id !== lessonId);
  }

  toggleType(type: InstructorQuestionType, checked: boolean): void {
    this.selectedTypes = checked
      ? [...this.selectedTypes, type]
      : this.selectedTypes.filter((value) => value !== type);
  }

  generate(): void {
    if (!this.canGenerate) return;
    const payload: QuestionPaperGeneratePayload = {
      course_id: this.courseId!,
      section_ids: this.selectedSectionIds,
      lesson_ids: this.selectedLessonIds,
      title: this.title.trim(),
      difficulty: this.difficulty,
      question_types: this.selectedTypes,
      question_count: Number(this.questionCount),
      total_marks: Number(this.totalMarks),
      duration_minutes: Number(this.durationMinutes),
      exam_date: this.examDate || null,
    };
    this.busy = true;
    this.instructorService.generateQuestionPaper(payload).subscribe({
      next: (paper) => {
        this.setPaper(paper);
        this.busy = false;
        this.showMessage('Question paper generated and saved as a draft. Review every question before publishing.');
        this.loadSavedPapers();
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not generate the question paper.');
      },
    });
  }

  openPaper(paperId: number): void {
    this.busy = true;
    this.instructorService.getQuestionPaper(paperId).subscribe({
      next: (paper) => {
        this.setPaper(paper);
        this.busy = false;
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not load this paper.');
      },
    });
  }

  deletePaper(paperId: number): void {
    const paper = this.savedPapers.find((item) => item.id === paperId);
    if (!paper || !window.confirm(`Delete "${paper.title}" and its answer key?`)) return;
    this.busy = true;
    this.instructorService.deleteQuestionPaper(paperId).subscribe({
      next: () => {
        if (this.paper?.id === paperId) this.paper = null;
        this.busy = false;
        this.showMessage('Question paper deleted.');
        this.loadSavedPapers();
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not delete this question paper.');
      },
    });
  }

  savePaper(): void {
    if (!this.paper) return;
    this.reorder();
    this.busy = true;
    this.instructorService.saveQuestionPaper(this.paper.id, {
      title: this.paper.title,
      total_marks: Number(this.paper.total_marks),
      duration_minutes: Number(this.paper.duration_minutes),
      difficulty: this.paper.difficulty,
      exam_date: this.paper.exam_date,
      questions: this.paper.questions,
    }).subscribe({
      next: (paper) => {
        this.setPaper(paper);
        this.busy = false;
        this.showMessage('Draft saved.');
        this.loadSavedPapers();
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not save this paper.');
      },
    });
  }

  publishPaper(): void {
    if (!this.paper || this.questionMarks !== this.paper.total_marks) return;
    this.saveBeforePublish();
  }

  addQuestion(): void {
    if (!this.paper) return;
    const order = this.paper.questions.length + 1;
    this.paper.questions.push({
      question_text: '',
      question_type: 'short_answer',
      difficulty: 'medium',
      marks: 1,
      options: [],
      correct_answer: '',
      explanation: '',
      question_order: order,
    });
    this.recalculateMarks();
  }

  deleteQuestion(index: number): void {
    if (!this.paper) return;
    this.paper.questions.splice(index, 1);
    this.reorder();
    this.recalculateMarks();
  }

  moveQuestion(index: number, delta: number): void {
    if (!this.paper) return;
    const target = index + delta;
    if (target < 0 || target >= this.paper.questions.length) return;
    [this.paper.questions[index], this.paper.questions[target]] = [
      this.paper.questions[target],
      this.paper.questions[index],
    ];
    this.reorder();
  }

  changeQuestionType(question: InstructorPaperQuestion): void {
    if (question.question_type === 'mcq') {
      question.options = question.options.length === 4 ? question.options : ['', '', '', ''];
      question.correct_answer = question.options[0];
    } else if (question.question_type === 'true_false') {
      question.options = [];
      question.correct_answer = 'True';
    } else {
      question.options = [];
      question.correct_answer = '';
    }
  }

  regenerateQuestion(question: InstructorPaperQuestion): void {
    if (!this.paper || !question.id) return;
    this.busy = true;
    this.instructorService.regeneratePaperQuestion(this.paper.id, question.id).subscribe({
      next: (paper) => {
        this.setPaper(paper);
        this.busy = false;
        this.showMessage('Question regenerated from the selected lesson content.');
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not regenerate this question.');
      },
    });
  }

  downloadPdf(answerKey: boolean): void {
    if (!this.paper) return;
    this.busy = true;
    this.instructorService.exportQuestionPaperPdf(this.paper.id, answerKey).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `eduverse-${this.paper!.id}-${answerKey ? 'answer-key' : 'question-paper'}.pdf`;
        link.click();
        URL.revokeObjectURL(url);
        this.busy = false;
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not export this PDF.');
      },
    });
  }

  letter(index: number): string {
    return String.fromCharCode(65 + index);
  }

  private saveBeforePublish(): void {
    if (!this.paper) return;
    this.savePaperAndPublish();
  }

  private savePaperAndPublish(): void {
    if (!this.paper) return;
    this.reorder();
    this.busy = true;
    this.instructorService.saveQuestionPaper(this.paper.id, {
      title: this.paper.title,
      total_marks: Number(this.paper.total_marks),
      duration_minutes: Number(this.paper.duration_minutes),
      difficulty: this.paper.difficulty,
      exam_date: this.paper.exam_date,
      questions: this.paper.questions,
    }).subscribe({
      next: (saved) => {
        this.instructorService.publishQuestionPaper(saved.id).subscribe({
          next: (published) => {
            this.setPaper(published);
            this.busy = false;
            this.showMessage('Question paper published. The answer key remains instructor-only.');
            this.loadSavedPapers();
          },
          error: (error: HttpErrorResponse) => {
            this.busy = false;
            this.showError(error, 'Could not publish this paper.');
          },
        });
      },
      error: (error: HttpErrorResponse) => {
        this.busy = false;
        this.showError(error, 'Could not save the paper before publishing.');
      },
    });
  }

  recalculateMarks(): void {
    if (this.paper) this.paper.total_marks = this.questionMarks;
  }

  private reorder(): void {
    if (this.paper) this.paper.questions.forEach((question, index) => question.question_order = index + 1);
  }

  private setPaper(paper: InstructorQuestionPaper): void {
    this.paper = {
      ...paper,
      questions: paper.questions.map((question) => ({
        ...question,
        options: [...(question.options ?? [])],
      })),
    };
    this.previewMode = false;
    this.showAnswerKey = false;
    this.courseId = paper.course_id;
    this.title = paper.title;
    this.totalMarks = paper.total_marks;
    this.durationMinutes = paper.duration_minutes;
    this.difficulty = paper.difficulty;
    this.examDate = paper.exam_date ?? '';
    this.selectedSectionIds = paper.section_ids;
    this.selectedLessonIds = paper.lesson_ids;
    this.instructorService.getTeachingCourseOutline(paper.course_id).subscribe({
      next: (outline) => this.outline = outline,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load paper source lessons.'),
    });
  }

  private loadSavedPapers(): void {
    this.instructorService.getQuestionPapers().subscribe({
      next: (items) => this.savedPapers = items,
      error: (error: HttpErrorResponse) => this.showError(error, 'Could not load saved papers.'),
    });
  }

  newPaper(): void {
    this.paper = null;
    this.courseId = null;
    this.outline = null;
    this.selectedLessonIds = [];
    this.selectedSectionIds = [];
    this.title = '';
  }

  setTotalMarks(value: number): void {
    if (this.paper) this.paper.total_marks = Number(value);
  }

  private showError(error: HttpErrorResponse, fallback: string): void {
    this.isError = true;
    const detail = error.error?.detail;
    this.message = typeof detail === 'string' ? detail : fallback;
  }

  private showMessage(message: string): void {
    this.message = message;
    this.isError = false;
  }
}
