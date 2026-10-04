import io
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, Client
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter
from accounts.forms import SignupForm
from accounts.models import Profile
from .models import Course, CourseVersion, Stage, Assignment, Enrollment, Submission, Certificate, GradeRevision
from .services import enroll, progress, submit_answer, grade_submission, issue_certificate
from .uploads import validate_text_file, validate_pdf

User = get_user_model()


def pdf_file():
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=200)
    output = io.BytesIO()
    writer.write(output)
    return SimpleUploadedFile('certificate.pdf', output.getvalue(), content_type='application/pdf')


class LearningTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_courses', stdout=io.StringIO())
        cls.user = User.objects.create_user('student@example.com', 'StrongPassword123!', first_name='رادوین', last_name='حسینی')
        cls.other = User.objects.create_user('other@example.com', 'StrongPassword123!')
        cls.admin = User.objects.create_superuser('teacher@example.com', 'StrongPassword123!')
        cls.python = Course.objects.get(slug='python')
        cls.csharp = Course.objects.get(slug='csharp')
        cls.enrollment = enroll(cls.user, cls.python)
        cls.stages = list(cls.enrollment.course_version.stages.all())

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.media = override_settings(MEDIA_ROOT=self.directory.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.addCleanup(self.directory.cleanup)

    def submit(self, stage=0):
        return submit_answer(self.user, self.enrollment.pk, self.stages[stage], 'print("solution")')

    def grade(self, submission, score, reason=''):
        revision = submission.grades.count()
        return grade_submission(self.admin, submission.pk, score, 'بازخورد آموزشی', reason, revision)

    def complete(self):
        submissions = []
        for i in range(4):
            s = self.submit(i)
            self.grade(s, 90)
            submissions.append(s)
        self.enrollment.refresh_from_db()
        return submissions

    def test_signup_normalizes_email_and_never_grants_admin(self):
        response = self.client.post(reverse('signup'), {'email': 'New@Example.COM', 'first_name': 'نام', 'last_name': 'خانوادگی',
             'password1': 'StrongPassword123!', 'password2': 'StrongPassword123!', 'is_staff': 'true', 'is_superuser': 'true'})
        self.assertRedirects(response, reverse('choose_courses'))
        user = User.objects.get(email='new@example.com')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('StrongPassword123!'))
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_duplicate_email_case_insensitive(self):
        form = SignupForm({'email': 'STUDENT@EXAMPLE.COM', 'first_name': 'a', 'last_name': 'b',
                           'password1': 'StrongPassword123!', 'password2': 'StrongPassword123!'})
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_login_normalizes_email(self):
        self.assertTrue(self.client.login(username='STUDENT@EXAMPLE.COM', password='StrongPassword123!'))

    def test_user_without_enrollment_resumes_onboarding(self):
        self.client.force_login(self.other)
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('choose_courses'))

    def test_choose_both_courses_and_hide_existing(self):
        self.client.force_login(self.other)
        response = self.client.post(reverse('choose_courses'), {'courses': [self.python.pk, self.csharp.pk]})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertEqual(self.other.enrollments.count(), 2)
        response = self.client.get(reverse('choose_courses'))
        self.assertFalse(response.context['available'].exists())

    def test_duplicate_enrollment_is_idempotent(self):
        same = enroll(self.user, self.python)
        self.assertEqual(same.pk, self.enrollment.pk)
        self.assertEqual(self.user.enrollments.count(), 1)

    def test_course_and_user_progress_independent(self):
        second = enroll(self.user, self.csharp)
        other = enroll(self.other, self.python)
        self.grade(self.submit(), 95)
        self.assertEqual(progress(self.enrollment)['percent'], 25)
        self.assertEqual(progress(second)['percent'], 0)
        self.assertEqual(progress(other)['percent'], 0)

    def test_locked_stage_get_and_post_denied(self):
        self.client.force_login(self.user)
        url = reverse('stage_detail', args=[self.stages[3].pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {'answer_text': 'x'}).status_code, 403)
        self.assertFalse(Submission.objects.exists())

    def test_foreign_course_assignment_rejected(self):
        foreign = self.csharp.versions.first().stages.first()
        with self.assertRaises(ValidationError):
            submit_answer(self.user, self.enrollment.pk, foreign, 'x')

    def test_submission_service_rejects_other_user(self):
        with self.assertRaises(PermissionDenied):
            submit_answer(self.other, self.enrollment.pk, self.stages[0], 'x')

    def test_pending_does_not_advance_and_blocks_second_answer(self):
        self.submit()
        self.assertEqual(progress(self.enrollment)['percent'], 0)
        with self.assertRaises(ValidationError):
            self.submit()
        self.assertEqual(Submission.objects.count(), 1)

    def test_boundary_69_70_71_and_revisions(self):
        s = self.submit()
        self.grade(s, 69)
        self.assertEqual(progress(self.enrollment)['percent'], 0)
        self.grade(s, 70, 'اصلاح')
        self.assertEqual(progress(self.enrollment)['percent'], 25)
        self.assertTrue(progress(self.enrollment)['rows'][1]['unlocked'])
        self.grade(s, 71, 'اصلاح')
        self.assertEqual(progress(self.enrollment)['percent'], 25)
        self.assertEqual(s.grades.count(), 3)
        self.assertTrue(progress(self.enrollment)['rows'][1]['unlocked'])

    def test_exactly_70_is_passing_and_completes_course(self):
        for index in range(4):
            submission = self.submit(index)
            self.grade(submission, 70)
            self.assertEqual(progress(self.enrollment)['percent'], 25 * (index + 1))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'completed')
        self.assertEqual(self.enrollment.certificate.status, 'pending')

    def test_upgrade_applies_rule_to_existing_70_grades(self):
        from importlib import import_module
        from types import SimpleNamespace
        from django.apps import apps
        self.complete()
        GradeRevision.objects.update(score=70)
        CourseVersion.objects.update(passing_operator='gt')
        Enrollment.objects.filter(pk=self.enrollment.pk).update(status='active', completed_at=None)
        Certificate.objects.all().delete()
        upgrade = import_module('learning.migrations.0002_inclusive_passing_grade')
        upgrade.apply_inclusive_policy(apps, SimpleNamespace(connection=connection))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.course_version.passing_operator, 'ge')
        self.assertEqual(self.enrollment.status, 'completed')
        self.assertEqual(progress(self.enrollment)['percent'], 100)
        self.assertEqual(self.enrollment.certificate.status, 'pending')
        self.assertEqual(GradeRevision.objects.filter(score=70).count(), 4)
        # Running the data correction twice must not duplicate certificates.
        upgrade.apply_inclusive_policy(apps, SimpleNamespace(connection=connection))
        self.assertEqual(Certificate.objects.count(), 1)

    def test_retry_preserves_original(self):
        s = self.submit()
        self.grade(s, 45)
        newer = self.submit()
        self.assertEqual(newer.attempt_number, 2)
        self.assertEqual(Submission.objects.count(), 2)
        self.grade(newer, 80)
        with self.assertRaises(ValidationError):
            self.submit()

    def test_invalid_score_rollback(self):
        s = self.submit()
        for score in (-1, 101):
            with self.assertRaises(ValidationError):
                self.grade(s, score)
        s.refresh_from_db()
        self.assertEqual(s.status, 'pending')
        self.assertEqual(s.grades.count(), 0)

    def test_change_reason_and_stale_review_required(self):
        s = self.submit()
        self.grade(s, 80)
        with self.assertRaises(ValidationError):
            self.grade(s, 60)
        with self.assertRaises(ValidationError):
            grade_submission(self.admin, s.pk, 60, 'feedback', 'reason', 0)
        self.assertEqual(s.grades.count(), 1)

    def test_staff_flag_alone_cannot_review(self):
        self.other.is_staff = True
        self.other.save()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('review_queue')).status_code, 403)
        with self.assertRaises(PermissionDenied):
            grade_submission(self.other, self.submit().pk, 100, 'x')

    def test_explicit_review_permission_works(self):
        self.other.is_staff = True
        self.other.save()
        self.other.user_permissions.add(Permission.objects.get(codename='review_submission'))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('review_queue')).status_code, 200)

    def test_reference_never_exposed_to_student(self):
        self.client.force_login(self.user)
        assignment = self.stages[0].assignment
        assignment.reference_text = 'PRIVATE-REFERENCE-SENTINEL'
        assignment.save()
        page = self.client.get(reverse('stage_detail', args=[self.stages[0].pk]))
        self.assertNotContains(page, 'PRIVATE-REFERENCE-SENTINEL')
        self.assertEqual(self.client.get(reverse('reference_file', args=[assignment.pk])).status_code, 403)

    def test_completion_creates_pending_certificate(self):
        self.complete()
        self.assertEqual(progress(self.enrollment)['percent'], 100)
        self.assertEqual(self.enrollment.status, 'completed')
        self.assertEqual(self.enrollment.certificate.status, 'pending')
        self.client.force_login(self.user)
        self.assertContains(self.client.get(reverse('certificates')), 'گواهی هنوز آماده نیست')

    def test_certificate_requires_complete_course(self):
        with self.assertRaises(ValidationError):
            issue_certificate(self.admin, self.enrollment.pk, pdf_file())
        self.assertFalse(Certificate.objects.exists())

    def test_pdf_download_owner_only(self):
        self.complete()
        certificate = issue_certificate(self.admin, self.enrollment.pk, pdf_file(), True)
        url = reverse('certificate_file', args=[certificate.public_id])
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response['Content-Disposition'])
        self.assertTrue(b''.join(response.streaming_content).startswith(b'%PDF'))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_regrade_revokes_certificate_and_relocks_later_stages(self):
        submissions = self.complete()
        cert = issue_certificate(self.admin, self.enrollment.pk, pdf_file())
        self.grade(submissions[0], 60, 'اشتباه در تصحیح')
        self.enrollment.refresh_from_db()
        cert.refresh_from_db()
        self.assertEqual(progress(self.enrollment)['percent'], 0)
        self.assertFalse(progress(self.enrollment)['rows'][1]['unlocked'])
        self.assertEqual(cert.status, 'revoked')
        self.assertEqual(self.enrollment.status, 'active')
        self.assertEqual(Submission.objects.count(), 4)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('certificate_file', args=[cert.public_id])).status_code, 404)
        self.grade(submissions[0], 80, 'تأیید دوباره')
        cert.refresh_from_db()
        self.assertEqual(cert.status, 'revoked')
        self.assertEqual(progress(self.enrollment)['percent'], 100)

    def test_submission_file_private(self):
        s = submit_answer(self.user, self.enrollment.pk, self.stages[0], file=SimpleUploadedFile('answer.py', b'print(1)'))
        url = reverse('submission_file', args=[s.pk])
        self.client.force_login(self.user)
        response = self.client.get(url)
        self.assertEqual(b''.join(response.streaming_content), b'print(1)')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get('/private-files-not-public/' + s.answer_file.name).status_code, 404)

    def test_invalid_uploads(self):
        for name, content in [('answer.exe', b'text'), ('answer.py', b'\x00\xff'), ('answer.txt', b'x' * (1024 * 1024 + 1))]:
            with self.assertRaises(ValidationError):
                validate_text_file(SimpleUploadedFile(name, content))
        with self.assertRaises(ValidationError):
            validate_pdf(SimpleUploadedFile('fake.pdf', b'%PDF-fake-content'))

    def test_avatar_reencoded_and_owner_only(self):
        data = io.BytesIO()
        Image.new('RGB', (30, 30), 'green').save(data, 'PNG')
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile'), {'first_name': 'رادوین', 'last_name': 'حسینی',
             'bio': 'Hello', 'avatar': SimpleUploadedFile('avatar.png', data.getvalue(), content_type='image/png')})
        self.assertRedirects(response, reverse('profile'))
        response = self.client.get(reverse('avatar'))
        raw = b''.join(response.streaming_content)
        self.assertEqual(Image.open(io.BytesIO(raw)).format, 'JPEG')
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(reverse('avatar')).status_code, 404)

    def test_invalid_avatar_is_form_error(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('profile'), {'first_name': 'A', 'last_name': 'B',
             'avatar': SimpleUploadedFile('x.png', b'not an image', content_type='image/png')})
        self.assertEqual(response.status_code, 200)
        self.assertIn('avatar', response.context['form'].errors)

    def test_unsafe_answer_is_escaped(self):
        submit_answer(self.user, self.enrollment.pk, self.stages[0], '<script>alert(1)</script>')
        self.client.force_login(self.user)
        page = self.client.get(reverse('stage_detail', args=[self.stages[0].pk]))
        self.assertNotContains(page, '<script>alert(1)</script>')
        self.assertContains(page, '&lt;script&gt;')

    def test_enrolled_course_content_cannot_change_in_admin_validation(self):
        stage = self.stages[0]
        stage.title = 'new'
        with self.assertRaises(ValidationError):
            stage.full_clean()
        with self.assertRaises(ValidationError):
            stage.assignment.full_clean()
        version = self.enrollment.course_version
        version.passing_threshold = 20
        with self.assertRaises(ValidationError):
            version.full_clean()

    def test_empty_version_cannot_publish(self):
        version = CourseVersion.objects.create(course=self.python, version=2)
        version.status = 'published'
        with self.assertRaises(ValidationError):
            version.full_clean()

    def test_new_version_does_not_change_existing_enrollment(self):
        version = CourseVersion.objects.create(course=self.python, version=2)
        stage = Stage.objects.create(course_version=version, position=1, title='V2', lesson_text='lesson')
        Assignment.objects.create(stage=stage, instructions='x', rubric='y', reference_text='z')
        version.status = 'published'
        version.full_clean()
        version.save()
        newer = enroll(self.other, self.python)
        self.assertEqual(newer.course_version_id, version.pk)
        self.enrollment.refresh_from_db()
        self.assertNotEqual(self.enrollment.course_version_id, version.pk)

    def test_seed_command_does_not_overwrite(self):
        self.grade(self.submit(), 85)
        call_command('seed_courses', stdout=io.StringIO())
        self.assertEqual(Course.objects.count(), 2)
        self.assertEqual(Stage.objects.count(), 8)
        self.assertEqual(progress(self.enrollment)['percent'], 25)

    def test_student_pages_and_admin_pages_render(self):
        self.client.force_login(self.user)
        for url in [reverse('home'), reverse('dashboard'), reverse('profile'), reverse('certificates'),
                    reverse('choose_courses'), reverse('course_detail', args=[self.enrollment.pk]),
                    reverse('stage_detail', args=[self.stages[0].pk])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.client.force_login(self.admin)
        for url in [reverse('admin:index'), reverse('admin:accounts_user_add'), reverse('admin:accounts_user_change', args=[self.user.pk]),
                    reverse('admin:learning_enrollment_changelist'), reverse('admin:learning_certificate_changelist'),
                    reverse('review_queue'), reverse('review_detail', args=[self.submit().pk])]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_review_form_updates_progress(self):
        s = self.submit()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('review_detail', args=[s.pk]), {'score': 85, 'feedback': 'آفرین', 'expected_revision': 0})
        self.assertRedirects(response, reverse('review_queue'))
        self.assertEqual(progress(self.enrollment)['percent'], 25)

    def test_certificate_upload_form(self):
        self.complete()
        self.client.force_login(self.admin)
        response = self.client.post(reverse('certificate_upload', args=[self.enrollment.pk]), {'file': pdf_file(), 'is_sample': True})
        self.assertRedirects(response, reverse('admin:learning_certificate_changelist'))
        self.assertEqual(Certificate.objects.get(enrollment=self.enrollment).status, 'available')

    def test_csrf_rejects_forged_submission(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('stage_detail', args=[self.stages[0].pk]), {'answer_text': 'x'}).status_code, 403)

    def test_password_reset_email(self):
        response = self.client.post(reverse('password_reset'), {'email': self.user.email})
        self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('/accounts/reset/', mail.outbox[0].body)

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_auth_rate_limit(self):
        for _ in range(20):
            response = self.client.post(reverse('login'), {'username': 'none@example.com', 'password': 'wrong'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.post(reverse('login'), {}).status_code, 429)


@skipUnless(connection.vendor == 'microsoft', 'Real row-lock tests require SQL Server (CI job).')
class ConcurrencyTests(TransactionTestCase):
    def setUp(self):
        call_command('seed_courses', stdout=io.StringIO())
        self.user = User.objects.create_user('concurrent@example.com', 'password')
        self.course = Course.objects.get(slug='python')
        self.admin = User.objects.create_superuser('reviewer@example.com', 'password')

    def race(self, action):
        barrier = Barrier(2)
        def run():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return action()
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(lambda _: run(), range(2)))

    def test_concurrent_enroll_only_one_row(self):
        results = self.race(lambda: enroll(User.objects.get(pk=self.user.pk), Course.objects.get(pk=self.course.pk)).pk)
        self.assertEqual(results[0], results[1])
        self.assertEqual(Enrollment.objects.count(), 1)

    def test_concurrent_submissions_only_one_pending(self):
        e = enroll(self.user, self.course)
        stage = e.course_version.stages.first()
        def action():
            try:
                submit_answer(User.objects.get(pk=self.user.pk), e.pk, stage, 'solution')
                return 'created'
            except ValidationError:
                return 'blocked'
        self.assertCountEqual(self.race(action), ['created', 'blocked'])
        self.assertEqual(Submission.objects.count(), 1)

    def test_concurrent_reviews_reject_stale_form(self):
        e = enroll(self.user, self.course)
        s = submit_answer(self.user, e.pk, e.course_version.stages.first(), 'solution')
        def action():
            try:
                grade_submission(User.objects.get(pk=self.admin.pk), s.pk, 90, 'feedback', expected_revision=0)
                return 'graded'
            except ValidationError:
                return 'stale'
        self.assertCountEqual(self.race(action), ['graded', 'stale'])
        self.assertEqual(GradeRevision.objects.count(), 1)
