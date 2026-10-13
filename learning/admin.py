from django.contrib import admin
from django.db import transaction
from django.urls import reverse
from django.utils.html import format_html
from .models import Course, CourseVersion, Stage, Assignment, Enrollment, Submission, GradeRevision, Certificate, AuditEvent
from .services import progress

admin.site.site_header = 'مدیریت test programing'
admin.site.site_title = 'test programing'
admin.site.index_title = 'دوره‌ها، دانشجوها و تکالیف'


class ProtectedAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Course)
class CourseAdmin(ProtectedAdmin):
    list_display = ('title', 'slug', 'is_active')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(CourseVersion)
class VersionAdmin(ProtectedAdmin):
    list_display = ('course', 'version', 'status', 'passing_threshold', 'passing_operator')
    readonly_fields = ('published_at',)

    def save_model(self, request, obj, form, change):
        from django.utils import timezone
        if obj.status == 'published' and not obj.published_at:
            obj.published_at = timezone.now()
        obj.save()

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        # Shares lock order with enrollment so publication edits cannot race first enrollment.
        if request.method == 'POST' and object_id:
            with transaction.atomic():
                CourseVersion.objects.select_for_update().filter(pk=object_id).first()
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)


class VersionContentAdmin(ProtectedAdmin):
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        if request.method == 'POST':
            with transaction.atomic():
                if self.model is Stage:
                    ids = set(Stage.objects.filter(pk=object_id).values_list('course_version_id', flat=True))
                    candidate = request.POST.get('course_version', '')
                    if candidate.isdigit():
                        ids.add(int(candidate))
                else:
                    ids = set(Assignment.objects.filter(pk=object_id).values_list('stage__course_version_id', flat=True))
                    candidate = request.POST.get('stage', '')
                    if candidate.isdigit():
                        ids.update(Stage.objects.filter(pk=candidate).values_list('course_version_id', flat=True))
                list(CourseVersion.objects.select_for_update().filter(pk__in=ids).order_by('pk'))
                return super().changeform_view(request, object_id, form_url, extra_context)
        return super().changeform_view(request, object_id, form_url, extra_context)


@admin.register(Stage)
class StageAdmin(VersionContentAdmin):
    list_display = ('title', 'course_version', 'position')
    list_filter = ('course_version__course',)


@admin.register(Assignment)
class AssignmentAdmin(VersionContentAdmin):
    list_display = ('stage',)


class ReadOnlyAdmin(ProtectedAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Enrollment)
class EnrollmentAdmin(ReadOnlyAdmin):
    list_display = ('user', 'course', 'status', 'progress_display', 'certificate_action')
    list_filter = ('course', 'status')
    search_fields = ('user__email',)

    @admin.display(description='پیشرفت')
    def progress_display(self, obj):
        return f"{progress(obj)['percent']}%"

    @admin.display(description='گواهی')
    def certificate_action(self, obj):
        if obj.status == 'completed' and not obj.user.is_learning_admin:
            return format_html('<a href="{}">بارگذاری گواهی</a>', reverse('certificate_upload', args=[obj.pk]))
        return '—'


@admin.register(Submission)
class SubmissionAdmin(ReadOnlyAdmin):
    list_display = ('enrollment', 'assignment', 'attempt_number', 'status', 'submitted_at', 'review_link')
    list_filter = ('status', 'enrollment__course')
    exclude = ('answer_file',)

    @admin.display(description='بررسی')
    def review_link(self, obj):
        return format_html('<a href="{}">مشاهده و نمره‌دهی</a>', reverse('review_detail', args=[obj.pk]))


@admin.register(GradeRevision)
class GradeAdmin(ReadOnlyAdmin):
    list_display = ('submission', 'score', 'revision', 'grader', 'graded_at')


@admin.register(Certificate)
class CertificateAdmin(ReadOnlyAdmin):
    list_display = ('enrollment', 'status', 'is_sample', 'issued_at', 'upload_link')
    exclude = ('file',)

    @admin.display(description='فایل PDF')
    def upload_link(self, obj):
        if obj.enrollment.user.is_learning_admin:
            return 'حساب مدیریتی — صدور غیرفعال'
        return format_html('<a href="{}">بارگذاری یا جایگزینی</a>', reverse('certificate_upload', args=[obj.enrollment_id]))


@admin.register(AuditEvent)
class AuditAdmin(ReadOnlyAdmin):
    list_display = ('actor', 'action', 'object_type', 'object_id', 'created_at')
