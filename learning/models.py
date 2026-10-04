import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from .uploads import upload_path, validate_text_file, validate_pdf, validate_material


class Course(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField('عنوان', max_length=200)
    description = models.TextField('توضیح')
    is_active = models.BooleanField('فعال', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class CourseVersion(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name='versions')
    version = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=[('draft', 'پیش‌نویس'), ('published', 'منتشرشده'), ('archived', 'بایگانی')], default='draft')
    passing_threshold = models.PositiveSmallIntegerField(default=70, validators=[MaxValueValidator(100)])
    passing_operator = models.CharField(max_length=2, choices=[('gt', 'بالاتر از'), ('ge', 'برابر یا بالاتر از')], default='ge')
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['course', 'version'], name='unique_course_version'),
                       models.CheckConstraint(condition=models.Q(version__gt=0), name='positive_version'),
                       models.CheckConstraint(condition=models.Q(passing_threshold__lte=100), name='threshold_range')]

    def passes(self, score):
        return score >= self.passing_threshold if self.passing_operator == 'ge' else score > self.passing_threshold

    def clean(self):
        if self.pk and self.enrollments.exists():
            old = CourseVersion.objects.get(pk=self.pk)
            if any(getattr(old, f) != getattr(self, f) for f in ('course_id', 'version', 'passing_threshold', 'passing_operator')):
                raise ValidationError('نسخه دارای دانشجو قابل تغییر ساختاری نیست؛ نسخه جدید بسازید.')
        if self.status == 'published':
            stages = list(self.stages.select_related('assignment').all()) if self.pk else []
            if not stages or [s.position for s in stages] != list(range(1, len(stages) + 1)):
                raise ValidationError('پیش از انتشار، مراحل متوالی از شماره ۱ بسازید.')
            if any(not hasattr(s, 'assignment') or not (s.assignment.reference_text or s.assignment.reference_file) for s in stages):
                raise ValidationError('هر مرحله به تکلیف و پاسخ مرجع نیاز دارد.')

    def __str__(self):
        return f'{self.course} / v{self.version}'


class Stage(models.Model):
    course_version = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name='stages')
    position = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    title = models.CharField('عنوان', max_length=200)
    lesson_text = models.TextField('متن درس')
    lesson_file = models.FileField(upload_to=upload_path, max_length=500, blank=True, validators=[validate_material])

    class Meta:
        ordering = ['position']
        constraints = [models.UniqueConstraint(fields=['course_version', 'position'], name='unique_stage_position'),
                       models.CheckConstraint(condition=models.Q(position__gt=0), name='positive_stage_position')]

    def clean(self):
        if self.course_version_id:
            versions = {self.course_version_id}
            if self.pk:
                versions.add(Stage.objects.get(pk=self.pk).course_version_id)
            if Enrollment.objects.filter(course_version_id__in=versions).exists():
                raise ValidationError('مراحل نسخه دارای دانشجو ثابت‌اند؛ نسخه جدید بسازید.')

    def __str__(self):
        return f'{self.course_version} / {self.position}: {self.title}'


class Assignment(models.Model):
    stage = models.OneToOneField(Stage, on_delete=models.PROTECT, related_name='assignment')
    instructions = models.TextField('صورت تکلیف')
    rubric = models.TextField('معیار نمره‌دهی')
    reference_text = models.TextField('پاسخ مرجع خصوصی', blank=True)
    reference_file = models.FileField(upload_to=upload_path, max_length=500, blank=True, validators=[validate_material])
    max_upload_bytes = models.PositiveIntegerField(default=1024 * 1024, validators=[MinValueValidator(1), MaxValueValidator(1024 * 1024)])

    def clean(self):
        if not (self.reference_text.strip() or self.reference_file):
            raise ValidationError('پاسخ مرجع متنی یا فایل لازم است.')
        if self.stage_id:
            stages = {self.stage_id}
            if self.pk:
                stages.add(Assignment.objects.get(pk=self.pk).stage_id)
            if Enrollment.objects.filter(course_version__stages__id__in=stages).exists():
                raise ValidationError('تکلیف نسخه دارای دانشجو ثابت است؛ نسخه جدید بسازید.')

    def __str__(self):
        return str(self.stage)


class Enrollment(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.PROTECT)
    course_version = models.ForeignKey(CourseVersion, on_delete=models.PROTECT, related_name='enrollments')
    status = models.CharField(max_length=20, choices=[('active', 'در حال یادگیری'), ('completed', 'تکمیل‌شده'), ('suspended', 'متوقف‌شده')], default='active')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'course'], name='unique_user_course')]
        indexes = [models.Index(fields=['user', 'status'])]

    def clean(self):
        if self.course_version_id and self.course_version.course_id != self.course_id:
            raise ValidationError('نسخه متعلق به این دوره نیست.')

    def __str__(self):
        return f'{self.user} / {self.course}'


class Submission(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.PROTECT, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.PROTECT)
    attempt_number = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    answer_text = models.TextField('پاسخ یا کد', blank=True, max_length=100000)
    answer_file = models.FileField('فایل پاسخ', upload_to=upload_path, max_length=500, blank=True, validators=[validate_text_file])
    status = models.CharField(max_length=20, choices=[('pending', 'منتظر بررسی'), ('graded', 'بررسی‌شده')], default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['enrollment', 'assignment', 'attempt_number'], name='unique_submission_attempt'),
                       models.CheckConstraint(condition=models.Q(attempt_number__gt=0), name='positive_attempt')]
        indexes = [models.Index(fields=['status', 'submitted_at']), models.Index(fields=['enrollment', 'assignment', 'submitted_at'])]
        permissions = [('review_submission', 'Can review submissions and private reference answers')]
        ordering = ['-submitted_at']

    def clean(self):
        if not (self.answer_text.strip() or self.answer_file):
            raise ValidationError('متن یا فایل پاسخ لازم است.')
        if self.enrollment_id and self.assignment_id and self.assignment.stage.course_version_id != self.enrollment.course_version_id:
            raise ValidationError('تکلیف متعلق به این ثبت‌نام نیست.')

    @property
    def latest_grade(self):
        return next(iter(self.grades.all()), None)

    def __str__(self):
        return f'{self.enrollment} / تلاش {self.attempt_number}'


class GradeRevision(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.PROTECT, related_name='grades')
    revision = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])
    grader = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    score = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    feedback = models.TextField('بازخورد', max_length=10000)
    change_reason = models.TextField('علت تغییر', blank=True, max_length=2000)
    graded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-revision']
        constraints = [models.UniqueConstraint(fields=['submission', 'revision'], name='unique_grade_revision'),
                       models.CheckConstraint(condition=models.Q(score__lte=100), name='grade_range'),
                       models.CheckConstraint(condition=models.Q(revision__gt=0), name='positive_revision')]


class Certificate(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.PROTECT, related_name='certificate')
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=[('pending', 'در انتظار فایل'), ('available', 'آماده دانلود'), ('revoked', 'باطل‌شده')], default='pending', db_index=True)
    file = models.FileField(upload_to=upload_path, max_length=500, blank=True, validators=[validate_pdf])
    student_name_snapshot = models.CharField(max_length=300, blank=True)
    course_title_snapshot = models.CharField(max_length=200, blank=True)
    is_sample = models.BooleanField('نمونه آزمایشی', default=False)
    issued_at = models.DateTimeField(null=True, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True)

    def __str__(self):
        return str(self.enrollment)


class AuditEvent(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=100)
    object_type = models.CharField(max_length=100)
    object_id = models.PositiveBigIntegerField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
