from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def require_student(user):
    if not user.is_authenticated or not user.is_active or user.is_learning_admin:
        raise PermissionDenied('این بخش مخصوص دانشجویان است؛ برای شرکت در دوره از حساب دانشجویی جدا استفاده کنید.')


def student_required(view):
    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        require_student(request.user)
        return view(request, *args, **kwargs)
    return wrapped
