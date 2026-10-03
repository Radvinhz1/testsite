from pathlib import Path
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from accounts.models import Profile
from .forms import CourseChoiceForm, SubmissionForm, GradeForm, CertificateForm
from .models import Course, Enrollment, Stage, Submission, Assignment, Certificate
from .services import enroll, progress, submit_answer, grade_submission, require_permission, issue_certificate


def home(request):
    courses = Course.objects.filter(is_active=True, versions__status='published').distinct()
    return render(request, 'learning/home.html', {'courses': courses})


def owned_enrollment(request, **filters):
    return get_object_or_404(Enrollment.objects.select_related('course', 'course_version', 'user'), user=request.user, **filters)


@login_required
def dashboard(request):
    enrollments = list(request.user.enrollments.select_related('course', 'course_version', 'certificate'))
    if not enrollments:
        return redirect('choose_courses')
    cards = [{'enrollment': e, 'state': progress(e)} for e in enrollments]
    return render(request, 'learning/dashboard.html', {'cards': cards, 'completed': sum(c['state']['complete'] for c in cards),
                    'passed': sum(c['state']['passed'] for c in cards)})


@login_required
def choose_courses(request):
    form = CourseChoiceForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                for course in form.cleaned_data['courses'].order_by('pk'):
                    enroll(request.user, course)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'دوره‌های شما اضافه شدند. وقت شروع یادگیری است!')
            return redirect('dashboard')
    return render(request, 'learning/choose.html', {'form': form, 'available': form.fields['courses'].queryset,
                   'onboarding': not request.user.enrollments.exists()})


@login_required
def course_detail(request, pk):
    enrollment = owned_enrollment(request, pk=pk)
    return render(request, 'learning/course.html', {'enrollment': enrollment, 'state': progress(enrollment)})


@login_required
def stage_detail(request, pk):
    stage = get_object_or_404(Stage.objects.select_related('assignment', 'course_version__course'), pk=pk)
    enrollment = owned_enrollment(request, course_version=stage.course_version)
    state = progress(enrollment)
    row = next(r for r in state['rows'] if r['stage'].pk == stage.pk)
    if not row['unlocked']:
        raise PermissionDenied('ابتدا مراحل قبلی را با موفقیت بگذرانید.')
    form = SubmissionForm(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        if not row['can_submit']:
            raise PermissionDenied
        if form.is_valid():
            try:
                submit_answer(request.user, enrollment.pk, stage, form.cleaned_data['answer_text'], form.cleaned_data.get('answer_file'))
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, 'پاسخ ثبت شد و منتظر بررسی مدرس است.')
                return redirect('stage_detail', pk=stage.pk)
    return render(request, 'learning/stage.html', {'stage': stage, 'enrollment': enrollment, 'row': row, 'form': form})


@login_required
def certificates(request):
    cards = [{'enrollment': e, 'state': progress(e)} for e in request.user.enrollments.select_related('course', 'course_version', 'certificate')]
    return render(request, 'learning/certificates.html', {'cards': cards})


def send_private(file, filename=None, inline=False):
    if not file:
        raise Http404
    try:
        response = FileResponse(file.open('rb'), as_attachment=not inline, filename=filename or Path(file.name).name)
    except FileNotFoundError:
        raise Http404
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Content-Security-Policy'] = "default-src 'none'; sandbox"
    return response


@login_required
def avatar(request):
    profile = get_object_or_404(Profile, user=request.user)
    return send_private(profile.avatar, 'avatar.jpg', inline=True)


@login_required
def submission_file(request, pk):
    submission = get_object_or_404(Submission.objects.select_related('enrollment'), pk=pk)
    if submission.enrollment.user_id != request.user.pk:
        require_permission(request.user, 'review_submission')
    return send_private(submission.answer_file)


@login_required
def reference_file(request, pk):
    require_permission(request.user, 'review_submission')
    return send_private(get_object_or_404(Assignment, pk=pk).reference_file)


@login_required
def lesson_file(request, pk):
    stage = get_object_or_404(Stage, pk=pk)
    enrollment = owned_enrollment(request, course_version_id=stage.course_version_id)
    row = next(r for r in progress(enrollment)['rows'] if r['stage'].pk == stage.pk)
    if not row['unlocked']:
        raise PermissionDenied
    return send_private(stage.lesson_file)


@login_required
def certificate_file(request, public_id):
    certificate = get_object_or_404(Certificate.objects.select_related('enrollment__course_version'), public_id=public_id)
    if certificate.enrollment.user_id != request.user.pk:
        require_permission(request.user, 'change_certificate')
    if certificate.status != 'available' or not progress(certificate.enrollment)['complete']:
        raise Http404
    return send_private(certificate.file, f'certificate-{certificate.public_id}.pdf')


@login_required
def review_queue(request):
    require_permission(request.user, 'review_submission')
    mode = request.GET.get('status', 'pending')
    submissions = Submission.objects.select_related('enrollment__user', 'enrollment__course', 'assignment__stage')
    if mode in {'pending', 'graded'}:
        submissions = submissions.filter(status=mode)
    page = Paginator(submissions, 25).get_page(request.GET.get('page'))
    return render(request, 'learning/reviews.html', {'page': page, 'mode': mode})


@login_required
def review_detail(request, pk):
    require_permission(request.user, 'review_submission')
    submission = get_object_or_404(Submission.objects.select_related('enrollment__user', 'assignment__stage'), pk=pk)
    latest = submission.latest_grade
    form = GradeForm(request.POST or None, initial={'expected_revision': latest.revision if latest else 0,
                                                   'score': latest.score if latest else None})
    if request.method == 'POST' and form.is_valid():
        try:
            grade_submission(request.user, submission.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'نمره ثبت شد و پیشرفت دانشجو به‌روز شد.')
            return redirect('review_queue')
    return render(request, 'learning/review_detail.html', {'submission': submission, 'form': form})


@login_required
def certificate_upload(request, pk):
    require_permission(request.user, 'change_certificate')
    enrollment = get_object_or_404(Enrollment.objects.select_related('user', 'course', 'course_version'), pk=pk)
    form = CertificateForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            issue_certificate(request.user, enrollment.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'گواهی بارگذاری شد.')
            return redirect('admin:learning_certificate_changelist')
    return render(request, 'learning/certificate_upload.html', {'form': form, 'enrollment': enrollment})
