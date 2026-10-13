from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path
from accounts import views as accounts
from accounts.forms import EmailLoginForm
from learning import views, seo

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('learn/<slug:slug>/', views.public_course, name='public_course'),
    path('robots.txt', seo.robots, name='robots'),
    path('sitemap.xml', seo.sitemap, name='sitemap'),
    path('accounts/signup/', accounts.signup, name='signup'),
    path('accounts/login/', accounts.RoleLoginView.as_view(authentication_form=EmailLoginForm), name='login'),
    path('accounts/logout/', auth.LogoutView.as_view(), name='logout'),
    path('accounts/profile/', accounts.profile, name='profile'),
    path('accounts/avatar/', views.avatar, name='avatar'),
    path('accounts/password-reset/', auth.PasswordResetView.as_view(), name='password_reset'),
    path('accounts/password-reset/done/', auth.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('accounts/reset/<uidb64>/<token>/', auth.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('accounts/reset/done/', auth.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('courses/choose/', views.choose_courses, name='choose_courses'),
    path('courses/<int:pk>/', views.course_detail, name='course_detail'),
    path('stages/<int:pk>/', views.stage_detail, name='stage_detail'),
    path('certificates/', views.certificates, name='certificates'),
    path('files/submissions/<int:pk>/', views.submission_file, name='submission_file'),
    path('files/references/<int:pk>/', views.reference_file, name='reference_file'),
    path('files/lessons/<int:pk>/', views.lesson_file, name='lesson_file'),
    path('files/certificates/<uuid:public_id>/', views.certificate_file, name='certificate_file'),
    path('staff/reviews/', views.review_queue, name='review_queue'),
    path('staff/reviews/<int:pk>/', views.review_detail, name='review_detail'),
    path('staff/certificates/<int:pk>/', views.certificate_upload, name='certificate_upload'),
]
