import os
import django.core.mail
from django.conf import settings
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session


class BogusSMTPConnection(object):
    """Instead of sending emails, print them to the console."""

    def __init__(self, *args, **kwargs):
        print "Initialized bogus SMTP connection"

    def open(self):
        print "Open bogus SMTP connection"

    def close(self):
        print "Clone bogus SMTP connection"

    def send_messages(self, messages):
        print "Sending through bogus SMTP connection:"
        for message in messages:
            print "From: %s" % message.from_email
            print "To: %s" % (", ".join(message.to))
            print "Subject: %s\n\n" % message.subject
            if os.sys.platform == 'win32':
                print "%s" % message.body.encode('cp866', 'replace')
            else:
                print "%s" % message.body
            print messages
        return len(messages)


def get_order_from_request(request, create=False):
    # avoid cross import
    from basket.models import Order
    uid = uid_from_request(request)
    return Order.objects.get_order(uid, create)

def uid_from_request(request):
    # if we won't request this variable, session wil not be created 
    session_key = request.session.session_key

    if request.user.is_authenticated():
        return request.user
    elif session_key:
        return session_key
    else:
        return None

def resolve_uid(uid):
    if type(uid) is str:
        try:
            session = Session.objects.get(pk=uid)
            return {'session': session}
        except Session.DoesNotExist:
            return {}
    elif type(uid) is User:
        return {'user': uid}
    else:
        return {}

def create_order_from_request(request):
    return get_order_from_request(request, create=True)

def send_mail(subject, message, recipent_list):
    from_email = settings.DEFAULT_FROM_EMAIL
    if type(recipent_list) is not list:
        recipent_list = [recipent_list, ]
    try:
        django.core.mail.send_mail(subject, message, from_email, recipent_list)
    except Exception, e:
        print 'Error while sending mail: ', e

def render_to(template_path):
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            output = func(request, *args, **kwargs)
            if output is None:
                output = {}
            if not isinstance(output, dict):
                return output
            return render_to_response(template_path, output,
                context_instance=RequestContext(request))
        return wrapper
    return decorator

def import_item(path, error_text):
    """Imports a model by given string. In error case raises ImpoprelyConfigured"""
    i = path.rfind('.')
    module, attr = path[:i], path[i + 1:]
    try:
        return getattr(__import__(module, {}, {}, ['']), attr)
    except ImportError, e:
        from django.core.exceptions import ImproperlyConfigured
        raise ImproperlyConfigured('Error importing %s %s: "%s"' % (error_text, path, e))
