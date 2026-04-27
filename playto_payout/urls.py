from django.contrib import admin
from django.urls import path, include, re_path
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.conf import settings
from pathlib import Path

def index(request):
    index_file = Path(settings.BASE_DIR) / 'frontend' / 'build' / 'index.html'
    if index_file.exists():
        return TemplateView.as_view(template_name='index.html')(request)
    return HttpResponse(
        '<h2>API is running.</h2>'
        '<p>Frontend build not found.</p>'
        '<p>API: <a href="/api/v1/merchants/">/api/v1/merchants/</a></p>',
        content_type='text/html'
    )

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/', include('payouts.urls')),
    re_path(r'^.*$', index),
]