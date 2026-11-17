from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_instructor
from app.models.user import User
from app.schemas.instructor_ai import (
    AssignmentEvaluationResponse,
    EvaluationEdit,
    InstructorCourseOption,
    InstructorSubmissionItem,
    PaperOutlineResponse,
    QuestionPaperGenerationRequest,
    QuestionPaperResponse,
    QuestionPaperSummary,
    QuestionPaperUpdate,
    RubricInput,
    RubricResponse,
)
from app.services.instructor_ai_service import (
    approve_assignment_evaluation,
    delete_question_paper,
    edit_assignment_evaluation,
    evaluate_submission,
    generate_question_paper,
    get_assignment_rubric,
    get_course_outline,
    get_question_paper,
    get_submission_attachment,
    list_instructor_submissions,
    list_instructor_teaching_courses,
    list_question_papers,
    publish_question_paper,
    render_question_paper_pdf,
    save_assignment_rubric,
    update_question_paper,
    regenerate_paper_question,
)
from app.services.instructor_ai_service import list_submission_evaluations, reevaluate_assignment_evaluation


router = APIRouter(prefix="/instructor/teaching", tags=["Instructor AI Teaching Tools"])


@router.get("/courses", response_model=list[InstructorCourseOption])
def teaching_courses(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_instructor_teaching_courses(db, current_user)


@router.get("/courses/{course_id}/outline", response_model=PaperOutlineResponse)
def teaching_course_outline(
    course_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_course_outline(db, course_id, current_user)


@router.get("/submissions", response_model=list[InstructorSubmissionItem])
def teaching_submissions(
    course_id: Optional[int] = None,
    assignment_id: Optional[int] = None,
    student_id: Optional[int] = None,
    submission_status: Optional[str] = None,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_instructor_submissions(
        db,
        current_user,
        course_id=course_id,
        assignment_id=assignment_id,
        student_id=student_id,
        submission_status=submission_status,
    )


@router.get("/assignments/{assignment_id}/rubric", response_model=RubricResponse)
def assignment_rubric(
    assignment_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_assignment_rubric(db, assignment_id, current_user)


@router.put("/assignments/{assignment_id}/rubric", response_model=RubricResponse)
def update_assignment_rubric(
    assignment_id: int,
    payload: RubricInput,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return save_assignment_rubric(db, assignment_id, current_user, payload)


@router.post(
    "/submissions/{submission_id}/evaluate",
    response_model=AssignmentEvaluationResponse,
)
def evaluate_student_submission(
    submission_id: int,
    force: bool = False,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return evaluate_submission(db, submission_id, current_user, force=force)


@router.get(
    "/submissions/{submission_id}/evaluations",
    response_model=list[AssignmentEvaluationResponse],
)
def submission_evaluation_history(
    submission_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_submission_evaluations(db, submission_id, current_user)


@router.get("/submissions/{submission_id}/attachments/{attachment_index}")
def download_submission_attachment(
    submission_id: int,
    attachment_index: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    content, filename, media_type = get_submission_attachment(
        db, submission_id, attachment_index, current_user
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}"},
    )


@router.put("/evaluations/{evaluation_id}", response_model=AssignmentEvaluationResponse)
def edit_ai_evaluation(
    evaluation_id: int,
    payload: EvaluationEdit,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return edit_assignment_evaluation(db, evaluation_id, current_user, payload)


@router.post("/evaluations/{evaluation_id}/approve", response_model=AssignmentEvaluationResponse)
def approve_ai_evaluation(
    evaluation_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return approve_assignment_evaluation(db, evaluation_id, current_user)


@router.post("/evaluations/{evaluation_id}/reevaluate", response_model=AssignmentEvaluationResponse)
def reevaluate_ai_suggestion(
    evaluation_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return reevaluate_assignment_evaluation(db, evaluation_id, current_user)


@router.get("/question-papers", response_model=list[QuestionPaperSummary])
def instructor_question_papers(
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return list_question_papers(db, current_user)


@router.post(
    "/question-papers/generate",
    response_model=QuestionPaperResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_ai_question_paper(
    payload: QuestionPaperGenerationRequest,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return generate_question_paper(db, current_user, payload)


@router.get("/question-papers/{paper_id}", response_model=QuestionPaperResponse)
def get_instructor_question_paper(
    paper_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return get_question_paper(db, paper_id, current_user)


@router.put("/question-papers/{paper_id}", response_model=QuestionPaperResponse)
def save_instructor_question_paper(
    paper_id: int,
    payload: QuestionPaperUpdate,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return update_question_paper(db, paper_id, current_user, payload)


@router.post(
    "/question-papers/{paper_id}/questions/{question_id}/regenerate",
    response_model=QuestionPaperResponse,
)
def regenerate_instructor_question(
    paper_id: int,
    question_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return regenerate_paper_question(db, paper_id, question_id, current_user)


@router.post("/question-papers/{paper_id}/publish", response_model=QuestionPaperResponse)
def publish_instructor_question_paper(
    paper_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return publish_question_paper(db, paper_id, current_user)


@router.delete("/question-papers/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_instructor_question_paper(
    paper_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    delete_question_paper(db, paper_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _paper_pdf_response(paper_id: int, current_user: User, db: Session, *, answer_key: bool) -> Response:
    from app.services.instructor_ai_service import get_paper_model

    paper = get_paper_model(db, paper_id, current_user)
    content = render_question_paper_pdf(paper, answer_key=answer_key)
    suffix = "answer-key" if answer_key else "question-paper"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="eduverse-{paper.id}-{suffix}.pdf"'},
    )


@router.get("/question-papers/{paper_id}/pdf")
def download_question_paper_pdf(
    paper_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return _paper_pdf_response(paper_id, current_user, db, answer_key=False)


@router.get("/question-papers/{paper_id}/answer-key.pdf")
def download_question_paper_answer_key(
    paper_id: int,
    current_user: User = Depends(require_instructor),
    db: Session = Depends(get_db),
):
    return _paper_pdf_response(paper_id, current_user, db, answer_key=True)
