"""Public metadata and indexing rules; private data never belongs in search results."""
import json
from xml.etree.ElementTree import Element, SubElement, tostring
from django.conf import settings
from django.http import HttpResponse
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe
from .models import Course

BRAND = 'test programing'
PUBLIC_PAGES = {'home', 'public_course'}
HOME_TITLE = 'آموزش برنامه‌نویسی پایتون و سی‌شارپ | test programing'
HOME_DESCRIPTION = 'آموزش برنامه‌نویسی پایتون و سی‌شارپ با تمرین مرحله‌ای، نمره‌دهی مدرس و پیگیری پیشرفت. دوره مناسب خودت را در test programing انتخاب کن.'


def public_courses():
    # Subquery avoids DISTINCT over SQL Server text columns and duplicate versions.
    return Course.objects.filter(is_active=True, versions__status='published').values('pk').distinct()


def metadata(request, title=HOME_TITLE, description=HOME_DESCRIPTION, schema=None):
    match = request.resolver_match
    public = bool(match and match.url_name in PUBLIC_PAGES)
    canonical = settings.SITE_URL + request.path if settings.SITE_URL and public else ''
    structured = ''
    if schema and canonical:
        # Prevent user-edited course text from closing the JSON-LD script element.
        structured = mark_safe(json.dumps(schema, ensure_ascii=False).replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e'))
    return {'seo_title': title, 'seo_description': ' '.join(strip_tags(description).split())[:170],
            'seo_canonical': canonical, 'seo_jsonld': structured,
            'seo_robots': 'index, follow' if public and settings.SEO_INDEXING_ENABLED else 'noindex, follow'}


def metadata_defaults(request):
    return metadata(request, title='test programing', description=HOME_DESCRIPTION)


class IndexingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        match = request.resolver_match
        if (not settings.SEO_INDEXING_ENABLED or response.status_code != 200
                or not match or match.url_name not in PUBLIC_PAGES):
            response['X-Robots-Tag'] = 'noindex, follow'
        return response


def robots(request):
    if settings.SEO_INDEXING_ENABLED:
        body = f'User-agent: *\nAllow: /\nSitemap: {settings.SITE_URL}/sitemap.xml\n'
    else:
        body = 'User-agent: *\nDisallow: /\n'
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


def sitemap(request):
    if not settings.SEO_INDEXING_ENABLED:
        return HttpResponse('Public indexing is not enabled.', status=503, content_type='text/plain')
    root = Element('urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
    paths = [reverse('home')]
    paths += [reverse('public_course', args=[slug]) for slug in
              Course.objects.filter(pk__in=public_courses()).order_by('slug').values_list('slug', flat=True)]
    for path in paths:
        url = SubElement(root, 'url')
        SubElement(url, 'loc').text = settings.SITE_URL + path
    return HttpResponse(tostring(root, encoding='utf-8', xml_declaration=True), content_type='application/xml')
