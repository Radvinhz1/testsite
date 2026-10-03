from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from learning.models import Course, CourseVersion, Stage, Assignment

RUBRIC = 'درستی نتیجه: ۶۰ امتیاز\nرعایت خواسته‌های سؤال: ۲۵ امتیاز\nخوانایی و ساختار کد: ۱۵ امتیاز'
PYTHON = [
    ('اولین برنامهٔ تو', 'متغیرها نامی برای نگهداری داده هستند. input یک متن از کاربر می‌گیرد و print نتیجه را نمایش می‌دهد. برای محاسبه عددی، ورودی را با int به عدد تبدیل کن.\nمثال:\nname = input("Name: ")\nprint("Hello", name)', 'نام و سن را دریافت کن؛ نام و سن سال آینده را چاپ کن. ورودی نمونه: Sara و 20؛ خروجی باید شامل Sara و 21 باشد.', 'name = input("Name: ")\nage = int(input("Age: "))\nprint(name, age + 1)'),
    ('تصمیم بگیر و تکرار کن', 'شرط if مسیر اجرای برنامه را انتخاب می‌کند. حلقه for کاری را چند بار انجام می‌دهد. باقی‌مانده تقسیم با % به دست می‌آید؛ عددی که باقی‌مانده تقسیمش بر ۲ صفر است، زوج است.', 'پنج عدد صحیح دریافت کن و تعداد اعداد زوج را چاپ کن. برای 1, 2, 3, 4, 6 نتیجه باید 3 باشد.', 'numbers = [int(input()) for _ in range(5)]\nprint(sum(1 for n in numbers if n % 2 == 0))'),
    ('تابع‌ها و داده‌ها', 'تابع یک بخش قابل استفاده مجدد از برنامه است. با def تابع را تعریف می‌کنیم و با return نتیجه را برمی‌گردانیم. لیست چند مقدار را در یک مجموعه نگه می‌دارد. حالت لیست خالی را فراموش نکن.', 'تابع average بنویس که میانگین یک لیست نمره را برگرداند. برای لیست خالی مقدار None بدهد. برای [10, 15, 20] نتیجه 15 است.', 'def average(scores):\n    return sum(scores) / len(scores) if scores else None'),
    ('پروژهٔ نهایی: فهرست کارها', 'حالا ورودی، شرط، حلقه، تابع و لیست را ترکیب کن. برنامه را به بخش‌های کوچک تقسیم کن: افزودن کار، نمایش کارها و خروج. این پروژه نمونه ساده خط فرمان است و نیازی به دیتابیس ندارد.', 'برنامه‌ای بساز که تا انتخاب خروج ادامه داشته باشد. کاربر بتواند یک کار اضافه کند و همه کارها را شماره‌گذاری‌شده ببیند. دستور نامعتبر باید پیام مناسب داشته باشد.', 'tasks = []\nwhile True:\n    action = input("add / list / quit: ")\n    if action == "quit":\n        break\n    elif action == "add":\n        tasks.append(input("Task: "))\n    elif action == "list":\n        for i, task in enumerate(tasks, 1):\n            print(i, task)\n    else:\n        print("Unknown command")'),
]
CSHARP = [
    ('اولین برنامه با سی‌شارپ', 'در برنامه Console، متد Console.ReadLine ورودی و Console.WriteLine خروجی را مدیریت می‌کند. نوع int برای عدد صحیح و string برای متن است. کدهای نمونه از دستورات سطح بالا استفاده می‌کنند.', 'نام و سن را دریافت کن و نام و سن سال آینده را چاپ کن. اگر سن عدد نبود، پیام مناسب بده.', 'using System;\nvar name = Console.ReadLine();\nif (int.TryParse(Console.ReadLine(), out int age))\n    Console.WriteLine($"{name} {age + 1}");\nelse\n    Console.WriteLine("Invalid age");'),
    ('شرط‌ها و حلقه‌ها', 'شرط if و حلقه for برای تصمیم و تکرار به کار می‌روند. عملگر % باقی‌مانده تقسیم را می‌دهد. با شمارنده می‌توان تعداد موارد مطابق یک شرط را نگه داشت.', 'پنج عدد صحیح معتبر دریافت کن و تعداد زوج‌ها را نمایش بده. برای 1, 2, 3, 4, 6 خروجی 3 است.', 'using System;\nint count = 0;\nfor (int i = 0; i < 5; i++)\n{\n    int number = int.Parse(Console.ReadLine()!);\n    if (number % 2 == 0) count++;\n}\nConsole.WriteLine(count);'),
    ('متد، کلاس و مجموعه', 'کلاس داده و رفتار مرتبط را کنار هم نگه می‌دارد. List مجموعه‌ای با اندازه متغیر است. متد می‌تواند نتیجه محاسبه روی داده‌های کلاس را برگرداند.', 'کلاس Student با نام و لیست نمرات بساز. متد Average میانگین نمرات را برگرداند و برای لیست خالی مقدار null بدهد.', 'using System.Collections.Generic;\nusing System.Linq;\nclass Student\n{\n    public string Name { get; set; } = "";\n    public List<double> Scores { get; set; } = new();\n    public double? Average() => Scores.Count == 0 ? null : Scores.Average();\n}'),
    ('پروژهٔ نهایی: فهرست کارها', 'یک برنامه تعاملی از ترکیب حلقه، شرط و مجموعه ساخته می‌شود. هر دستور را جدا مدیریت کن. خروج باید حلقه را تمام کند و دستور نامعتبر نباید برنامه را متوقف کند.', 'برنامه Console با دستورهای add، list و quit بساز. کارها در List نگهداری و شماره‌گذاری شوند؛ برای دستور ناشناخته پیام بده.', 'using System;\nusing System.Collections.Generic;\nvar tasks = new List<string>();\nwhile (true)\n{\n    var action = Console.ReadLine();\n    if (action == "quit" || action is null) break;\n    if (action == "add") tasks.Add(Console.ReadLine() ?? "");\n    else if (action == "list")\n        for (int i = 0; i < tasks.Count; i++) Console.WriteLine($"{i + 1}. {tasks[i]}");\n    else Console.WriteLine("Unknown command");\n}'),
]


class Command(BaseCommand):
    help = 'Create two sample courses without modifying existing courses or student progress.'

    @transaction.atomic
    def handle(self, *args, **options):
        for slug, title, description, lessons in [
            ('python', 'برنامه‌نویسی با پایتون', 'از اولین خط کد تا ساخت یک برنامه واقعی؛ ساده، کاربردی و قدم‌به‌قدم.', PYTHON),
            ('csharp', 'برنامه‌نویسی با سی‌شارپ', 'با منطق برنامه‌نویسی و ساختارهای شیءگرا آشنا شو و اولین پروژه‌ات را بساز.', CSHARP),
        ]:
            course, created = Course.objects.get_or_create(slug=slug, defaults={'title': title, 'description': description})
            if not created:
                self.stdout.write(f'Skipped existing course: {slug}')
                continue
            version = CourseVersion.objects.create(course=course)
            for index, (name, lesson, prompt, reference) in enumerate(lessons, 1):
                stage = Stage.objects.create(course_version=version, position=index, title=name, lesson_text=lesson)
                Assignment.objects.create(stage=stage, instructions=prompt, rubric=RUBRIC, reference_text=reference)
            version.status = 'published'
            version.published_at = timezone.now()
            version.full_clean()
            version.save()
            self.stdout.write(self.style.SUCCESS(f'Created {slug}: 4 stages (sample content).'))
