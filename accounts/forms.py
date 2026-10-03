from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User, Profile
from learning.uploads import sanitize_avatar


class SignupForm(UserCreationForm):
    first_name = forms.CharField(label='نام', max_length=150)
    last_name = forms.CharField(label='نام خانوادگی', max_length=150)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email')

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('این ایمیل قبلاً ثبت شده است.')
        return email


class EmailLoginForm(AuthenticationForm):
    username = forms.EmailField(label='ایمیل', widget=forms.EmailInput(attrs={'autocomplete': 'email', 'dir': 'ltr'}))


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(label='نام', max_length=150)
    last_name = forms.CharField(label='نام خانوادگی', max_length=150)
    avatar = forms.FileField(label='عکس پروفایل', required=False, widget=forms.FileInput(attrs={'accept': 'image/jpeg,image/png,image/webp'}))

    class Meta:
        model = Profile
        fields = ('first_name', 'last_name', 'bio', 'avatar')

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        return sanitize_avatar(avatar) if avatar else self.instance.avatar
