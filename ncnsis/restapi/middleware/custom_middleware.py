from django.conf import settings
from django.http import HttpRequest

class CustomAbsoluteURI:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        response = self.get_response(request)
        if not settings.DEBUG:
            request.build_absolute_uri = lambda path: settings.BASE_URL + path
        return response