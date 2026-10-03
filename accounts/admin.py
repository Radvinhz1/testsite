from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, AdminUserCreationForm
from .models import User, Profile


class AddUserForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ('email',)


class ChangeUserForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class AccountAdmin(UserAdmin):
    form = ChangeUserForm
    add_form = AddUserForm
    ordering = ('email',)
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active')
    search_fields = ('email', 'first_name', 'last_name')
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('مشخصات', {'fields': ('first_name', 'last_name')}),
                 ('مجوزها', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
                 ('زمان‌ها', {'fields': ('last_login', 'date_joined')}))
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'first_name', 'last_name', 'password1', 'password2')}),)

    def has_change_permission(self, request, obj=None):
        # User-management permission alone must not allow privilege escalation.
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'updated_at')
    readonly_fields = ('user', 'bio', 'updated_at')
    exclude = ('avatar',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
