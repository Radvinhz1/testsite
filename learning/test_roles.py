import io
import tempfile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Course, Enrollment, Certificate, Submission
from .services import enroll, submit_answer, grade_submission, issue_certificate
from .tests import pdf_file

User = get_user_model()


class RoleSeparationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_courses', stdout=io.StringIO())
        cls.student = User.objects.create_user('learner@example.com', 'StrongPassword123!')
        cls.staff = User.objects.create_user('staff@example.com', 'StrongPassword123!', is_staff=True)
        cls.admin = User.objects.create_superuser('admin@example.com', 'StrongPassword123!')
        cls.course = Course.objects.get(slug='python')
        cls.enrollment = enroll(cls.student, cls.course)
        cls.stage = cls.enrollment.course_version.stages.first()

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        override = override_settings(MEDIA_ROOT=directory.name)
        override.enable()
        self.addCleanup(override.disable)

    def promote(self):
        User.objects.filter(pk=self.student.pk).update(is_staff=True)
        self.student.refresh_from_db()

    def test_staff_and_superuser_cannot_enroll_via_service_or_http(self):
        for user in [self.staff, self.admin]:
            with self.subTest(user=user.email):
                with self.assertRaises(PermissionDenied):
                    enroll(user, self.course)
                self.client.force_login(user)
                for method in [self.client.get, self.client.post]:
                    response = method(reverse('choose_courses'), {'courses': [self.course.pk]})
                    self.assertEqual(response.status_code, 403)
                self.assertFalse(Enrollment.objects.filter(user=user).exists())
                candidate = Enrollment(user=user, course=self.course, course_version=self.enrollment.course_version)
                with self.assertRaises(ValidationError):
                    candidate.full_clean()

    def test_admin_login_ignores_student_next_and_dashboard_redirects(self):
        for user in [self.admin, self.staff]:
            self.client.logout()
            response = self.client.post(reverse('login'), {
                'username': user.email, 'password': 'StrongPassword123!', 'next': reverse('choose_courses')})
            self.assertRedirects(response, reverse('admin:index'), fetch_redirect_response=False)
            self.assertRedirects(self.client.get(reverse('dashboard')), reverse('admin:index'), fetch_redirect_response=False)
            self.assertRedirects(self.client.get(reverse('signup')), reverse('admin:index'), fetch_redirect_response=False)

    def test_student_login_and_enrollment_still_work(self):
        response = self.client.post(reverse('login'), {
            'username': self.student.email, 'password': 'StrongPassword123!', 'next': reverse('choose_courses')})
        self.assertRedirects(response, reverse('choose_courses'))
        second = Course.objects.get(slug='csharp')
        response = self.client.post(reverse('choose_courses'), {'courses': [second.pk]})
        self.assertRedirects(response, reverse('dashboard'))
        self.assertTrue(Enrollment.objects.filter(user=self.student, course=second).exists())
        response = self.client.post(reverse('stage_detail', args=[self.stage.pk]), {'answer_text': 'print(1)'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Submission.objects.filter(enrollment=self.enrollment).exists())

    def test_promoted_student_cannot_use_existing_enrollment(self):
        stale_user = User.objects.get(pk=self.student.pk)
        self.promote()
        self.client.force_login(self.student)
        for path in [reverse('course_detail', args=[self.enrollment.pk]),
                     reverse('stage_detail', args=[self.stage.pk]), reverse('certificates')]:
            self.assertEqual(self.client.get(path).status_code, 403)
        self.assertEqual(self.client.post(reverse('stage_detail', args=[self.stage.pk]), {'answer_text': 'print(1)'}).status_code, 403)
        with self.assertRaises(PermissionDenied):
            submit_answer(stale_user, self.enrollment.pk, self.stage, 'print(1)')
        with self.assertRaises(PermissionDenied):
            enroll(stale_user, self.course)
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())
        self.assertFalse(Submission.objects.filter(enrollment=self.enrollment).exists())

    def test_cannot_grade_old_submission_after_student_promoted(self):
        submission = submit_answer(self.student, self.enrollment.pk, self.stage, 'print(1)')
        self.promote()
        with self.assertRaises(PermissionDenied):
            grade_submission(self.admin, submission.pk, 90, 'feedback')
        self.assertFalse(submission.grades.exists())

    def test_promoted_student_cannot_receive_or_download_own_certificate(self):
        for stage in self.enrollment.course_version.stages.all():
            submission = submit_answer(self.student, self.enrollment.pk, stage, 'answer')
            grade_submission(self.admin, submission.pk, 70, 'passed')
        certificate = issue_certificate(self.admin, self.enrollment.pk, pdf_file())
        self.promote()
        with self.assertRaises(PermissionDenied):
            issue_certificate(self.admin, self.enrollment.pk, pdf_file())
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse('certificate_file', args=[certificate.public_id])).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('certificate_upload', args=[self.enrollment.pk])).status_code, 403)
        self.assertTrue(Certificate.objects.filter(pk=certificate.pk).exists())

    def test_admin_can_manage_student_and_read_lesson_with_permission(self):
        self.stage.lesson_file.save('lesson.txt', SimpleUploadedFile('lesson.txt', b'lesson'))
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('lesson_file', args=[self.stage.pk])).status_code, 403)
        self.staff.user_permissions.add(Permission.objects.get(codename='view_stage'))
        response = self.client.get(reverse('lesson_file', args=[self.stage.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"lesson")
        submission = submit_answer(self.student, self.enrollment.pk, self.stage, 'answer')
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('review_detail', args=[submission.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin:learning_course_change', args=[self.course.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('certificate_upload', args=[self.enrollment.pk])).status_code, 200)

    def test_admin_ui_has_no_student_navigation_or_enrollment_cta(self):
        self.client.force_login(self.admin)
        for path in [reverse('home'), reverse('public_course', args=['python']), reverse('profile')]:
            response = self.client.get(path)
            self.assertContains(response, reverse('admin:index'))
            self.assertNotContains(response, 'href="' + reverse('dashboard') + '"')
            self.assertNotContains(response, 'href="' + reverse('choose_courses') + '"')
            self.assertNotContains(response, 'href="' + reverse('certificates') + '"')
        self.client.force_login(self.student)
        self.assertContains(self.client.get(reverse('home')), 'href="' + reverse('dashboard') + '"')

    def test_anonymous_student_pages_still_require_login(self):
        self.assertRedirects(self.client.get(reverse('choose_courses')), reverse('login') + '?next=/courses/choose/')
