from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from .models import CourseVersion, Enrollment, Submission, GradeRevision, Certificate, AuditEvent
from .uploads import validate_text_file, validate_pdf


def require_permission(user, name):
    if not user.is_active or not user.is_staff or not user.has_perm(f'learning.{name}'):
        raise PermissionDenied


def progress(enrollment):
    stages = list(enrollment.course_version.stages.select_related('assignment'))
    submissions = list(enrollment.submissions.select_related('assignment').prefetch_related('grades'))
    by_assignment = {}
    for submission in submissions:
        by_assignment.setdefault(submission.assignment_id, []).append(submission)
    open_path = enrollment.status != 'suspended'
    passed_count = 0
    rows = []
    for stage in stages:
        attempts = by_assignment.get(stage.assignment.pk, []) if hasattr(stage, 'assignment') else []
        passed = any(s.latest_grade and enrollment.course_version.passes(s.latest_grade.score) for s in attempts)
        pending = any(s.status == 'pending' for s in attempts)
        unlocked = open_path
        valid_pass = unlocked and passed
        if valid_pass:
            passed_count += 1
        status = 'locked' if not unlocked else ('passed' if passed else ('pending' if pending else ('retry' if attempts else 'open')))
        labels = {'locked': 'قفل', 'passed': 'قبول‌شده', 'pending': 'منتظر بررسی', 'retry': 'نیازمند اصلاح', 'open': 'آماده شروع'}
        rows.append({'stage': stage, 'status': status, 'label': labels[status], 'unlocked': unlocked,
                     'can_submit': unlocked and not passed and not pending, 'attempts': attempts})
        open_path = open_path and passed
    return {'rows': rows, 'passed': passed_count, 'total': len(stages),
            'percent': round(100 * passed_count / len(stages)) if stages else 0,
            'complete': bool(stages) and passed_count == len(stages)}


@transaction.atomic
def enroll(user, course):
    # Serializes repeated enrollment requests, including choosing both courses.
    get_user_model().objects.select_for_update().get(pk=user.pk)
    existing = Enrollment.objects.filter(user=user, course=course).first()
    if existing:
        return existing
    version = CourseVersion.objects.select_for_update().filter(course=course, course__is_active=True, status='published').order_by('-version').first()
    if not version:
        raise ValidationError('این دوره فعلاً قابل ثبت‌نام نیست.')
    version.full_clean()
    enrollment = Enrollment(user=user, course=course, course_version=version)
    enrollment.full_clean()
    enrollment.save()
    return enrollment


@transaction.atomic
def submit_answer(user, enrollment_id, stage, text='', file=None):
    enrollment = Enrollment.objects.select_for_update().select_related('course_version').get(pk=enrollment_id)
    if enrollment.user_id != user.pk:
        raise PermissionDenied
    row = next((r for r in progress(enrollment)['rows'] if r['stage'].pk == stage.pk), None)
    if not row or not row['can_submit']:
        raise ValidationError('ارسال تکلیف این مرحله اکنون مجاز نیست.')
    if file:
        validate_text_file(file, stage.assignment.max_upload_bytes)
    attempts = enrollment.submissions.filter(assignment=stage.assignment)
    attempt = (attempts.aggregate(n=Max('attempt_number'))['n'] or 0) + 1
    submission = Submission(enrollment=enrollment, assignment=stage.assignment, attempt_number=attempt,
                            answer_text=text, answer_file=file)
    submission.full_clean()
    submission.save()
    return submission


def sync_completion(enrollment):
    state = progress(enrollment)
    if enrollment.status == 'suspended':
        Certificate.objects.filter(enrollment=enrollment).update(status='revoked')
        return
    if state['complete']:
        enrollment.status = 'completed'
        enrollment.completed_at = enrollment.completed_at or timezone.now()
        # A revoked document needs explicit reissue by an administrator.
        Certificate.objects.get_or_create(enrollment=enrollment)
    else:
        enrollment.status = 'active'
        enrollment.completed_at = None
        Certificate.objects.filter(enrollment=enrollment).exclude(status='revoked').update(status='revoked')
    enrollment.save(update_fields=['status', 'completed_at'])


@transaction.atomic
def grade_submission(user, submission_id, score, feedback, change_reason='', expected_revision=0):
    require_permission(user, 'review_submission')
    owner_id = Submission.objects.values_list('enrollment_id', flat=True).get(pk=submission_id)
    enrollment = Enrollment.objects.select_for_update().select_related('course_version', 'user', 'course').get(pk=owner_id)
    submission = Submission.objects.select_for_update().get(pk=submission_id)
    latest = submission.latest_grade
    current_revision = latest.revision if latest else 0
    if expected_revision != current_revision:
        raise ValidationError('این پاسخ هم‌زمان بررسی شده است؛ صفحه را تازه کنید و دوباره تصمیم بگیرید.')
    if latest and not change_reason.strip():
        raise ValidationError('برای اصلاح نمره، علت تغییر را بنویسید.')
    grade = GradeRevision(submission=submission, revision=current_revision + 1, grader=user,
                          score=score, feedback=feedback, change_reason=change_reason)
    grade.full_clean()
    grade.save()
    submission.status = 'graded'
    submission.save(update_fields=['status'])
    sync_completion(enrollment)
    AuditEvent.objects.create(actor=user, action='grade', object_type='submission', object_id=submission.pk,
                              metadata={'revision': grade.revision, 'score': score})
    return grade


@transaction.atomic
def issue_certificate(user, enrollment_id, file, is_sample=False):
    require_permission(user, 'change_certificate')
    enrollment = Enrollment.objects.select_for_update().select_related('course_version', 'user', 'course').get(pk=enrollment_id)
    if not progress(enrollment)['complete']:
        raise ValidationError('گواهی فقط برای دوره تکمیل‌شده صادر می‌شود.')
    validate_pdf(file)
    if not file:
        raise ValidationError('فایل PDF لازم است.')
    certificate, _ = Certificate.objects.get_or_create(enrollment=enrollment)
    certificate.file = file
    certificate.status = 'available'
    certificate.student_name_snapshot = enrollment.user.get_full_name() or enrollment.user.email
    certificate.course_title_snapshot = enrollment.course.title
    certificate.is_sample = is_sample
    certificate.issued_at = timezone.now()
    certificate.uploaded_by = user
    certificate.full_clean()
    certificate.save()
    AuditEvent.objects.create(actor=user, action='issue_certificate', object_type='certificate', object_id=certificate.pk,
                              metadata={'is_sample': is_sample})
    return certificate
