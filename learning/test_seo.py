import io
import json
import re
from xml.etree import ElementTree
from django.core.management import call_command
from django.test import TestCase, override_settings
from .models import Course, CourseVersion, Assignment


@override_settings(SITE_URL='https://courses.example.com', SEO_INDEXING_ENABLED=True)
class SEOTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_courses', stdout=io.StringIO())

    def test_home_metadata_canonical_and_public_links(self):
        response = self.client.get('/?utm_source=test')
        self.assertContains(response, '<title>آموزش برنامه‌نویسی پایتون و سی‌شارپ | test programing</title>', html=True)
        self.assertContains(response, 'href="https://courses.example.com/"')
        self.assertContains(response, 'href="/learn/python/"')
        self.assertNotIn('X-Robots-Tag', response)
        self.assertContains(response, 'content="index, follow"')

    def test_public_syllabus_excludes_private_material(self):
        assignment = Assignment.objects.filter(stage__course_version__course__slug='python').first()
        assignment.reference_text = 'PRIVATE_REFERENCE_SENTINEL'
        assignment.instructions = 'PRIVATE_ASSIGNMENT_SENTINEL'
        assignment.save()
        response = self.client.get('/learn/python/')
        self.assertContains(response, assignment.stage.title)
        self.assertContains(response, '70')
        self.assertNotContains(response, 'PRIVATE_REFERENCE_SENTINEL')
        self.assertNotContains(response, 'PRIVATE_ASSIGNMENT_SENTINEL')
        self.assertNotContains(response, assignment.stage.lesson_text)

    def test_sitemap_only_published_active_public_pages(self):
        draft = Course.objects.create(slug='draft', title='Draft', description='Hidden')
        CourseVersion.objects.create(course=draft)
        course = Course.objects.get(slug='python')
        CourseVersion.objects.create(course=course, version=2, status='published')
        response = self.client.get('/sitemap.xml')
        root = ElementTree.fromstring(response.content)
        urls = [node.text for node in root.findall('{*}url/{*}loc')]
        self.assertEqual(set(urls), {'https://courses.example.com/', 'https://courses.example.com/learn/python/', 'https://courses.example.com/learn/csharp/'})
        self.assertEqual(len(urls), 3)
        self.assertEqual(self.client.get('/learn/draft/').status_code, 404)
        course.is_active = False
        course.save()
        self.assertEqual(self.client.get('/learn/python/').status_code, 404)
        self.assertNotContains(self.client.get('/sitemap.xml'), '/learn/python/')

    def test_private_auth_and_error_responses_are_noindex(self):
        for path in ['/accounts/login/', '/accounts/signup/', '/dashboard/', '/admin/login/', '/staff/reviews/', '/files/submissions/999/', '/missing/', '/learn/missing/']:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path)['X-Robots-Tag'], 'noindex, follow')

    def test_schema_safely_encodes_course_content(self):
        course = Course.objects.get(slug='python')
        course.description = '</script><script>alert("test")</script> & details'
        course.save()
        response = self.client.get('/learn/python/')
        html = response.content.decode()
        encoded = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
        self.assertEqual(json.loads(encoded)['description'], course.description)
        self.assertNotIn('<script>alert', html)

    def test_robots_advertises_canonical_sitemap(self):
        response = self.client.get('/robots.txt')
        self.assertContains(response, 'Sitemap: https://courses.example.com/sitemap.xml')
        self.assertNotContains(response, 'Disallow: /')

    @override_settings(SITE_URL='', SEO_INDEXING_ENABLED=False)
    def test_unconfigured_preview_is_not_indexable(self):
        response = self.client.get('/')
        self.assertEqual(response['X-Robots-Tag'], 'noindex, follow')
        self.assertNotContains(response, 'rel="canonical"')
        self.assertNotContains(response, 'application/ld+json')
        self.assertContains(self.client.get('/robots.txt'), 'Disallow: /')
        self.assertEqual(self.client.get('/sitemap.xml').status_code, 503)
