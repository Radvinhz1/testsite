from django import forms
from .models import Course
from .uploads import validate_text_file, validate_pdf


class CourseChoiceForm(forms.Form):
    courses = forms.ModelMultipleChoiceField(label='مسیر یادگیری‌ات را انتخاب کن', queryset=Course.objects.none(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['courses'].queryset = Course.objects.filter(is_active=True, versions__status='published').exclude(enrollment__user=user).distinct()


class SubmissionForm(forms.Form):
    answer_text = forms.CharField(label='پاسخ یا کد', required=False, max_length=100000,
                                  widget=forms.Textarea(attrs={'rows': 12, 'dir': 'ltr', 'spellcheck': 'false', 'placeholder': '# Write your solution here…'}))
    answer_file = forms.FileField(label='یا فایل پاسخ', required=False, validators=[validate_text_file],
                                  help_text='فایل py، cs یا txt با کدگذاری UTF-8؛ حداکثر یک مگابایت.')

    def clean(self):
        data = super().clean()
        if not (data.get('answer_text', '').strip() or data.get('answer_file')):
            raise forms.ValidationError('کد را بنویسید یا فایل پاسخ را انتخاب کنید.')
        return data


class GradeForm(forms.Form):
    score = forms.IntegerField(label='نمره از ۱۰۰', min_value=0, max_value=100)
    feedback = forms.CharField(label='بازخورد برای دانشجو', max_length=10000, widget=forms.Textarea(attrs={'rows': 4}))
    change_reason = forms.CharField(label='علت اصلاح نمره (برای بررسی مجدد الزامی)', required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 2}))
    expected_revision = forms.IntegerField(widget=forms.HiddenInput, min_value=0)


class CertificateForm(forms.Form):
    file = forms.FileField(label='فایل گواهی PDF', validators=[validate_pdf])
    is_sample = forms.BooleanField(label='این فایل نمونه آزمایشی است', required=False)
