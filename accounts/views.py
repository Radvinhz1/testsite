from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction, IntegrityError
from django.shortcuts import redirect, render
from .forms import SignupForm, ProfileForm
from .models import Profile


def signup(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                Profile.objects.create(user=user)
        except IntegrityError:
            form.add_error('email', 'این ایمیل قبلاً ثبت شده است.')
        else:
            login(request, user, backend='accounts.backends.EmailBackend')
            return redirect('choose_courses')
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def profile(request):
    obj, _ = Profile.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, request.FILES or None, instance=obj,
                       initial={'first_name': request.user.first_name, 'last_name': request.user.last_name})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.save(update_fields=['first_name', 'last_name'])
            form.save()
        messages.success(request, 'پروفایل شما به‌روز شد.')
        return redirect('profile')
    return render(request, 'registration/profile.html', {'form': form, 'profile': obj})
