from django.http import HttpResponse
from django.template import Context
from django.template.loader import render_to_string, get_template
from django.core.mail import EmailMessage
from django.conf import settings
from django.core.exceptions import ValidationError
from ledger.accounts.models import EmailUser
from applications.models import Referral
from confy import env
from applications import models
from django.core.files import File
from django.core.files.base import ContentFile

import hashlib
import datetime
"""
Email Delivery will only work when EMAIL_DELIVERY is switched on.  To accidently stop invalid emails going out to end users.
If your local developement area doesn't have a email catch all setup you can use the override flag 'OVERRIDE_EMAIL' to send all email generated to a specfic address.

To enable the variable please add them to your .env

eg.

EMAIL_DELIVERY=on
OVERRIDE_EMAIL=jason.moore@dpaw.wa.gov.au

"""


def sendHtmlEmail(to,subject,context,template,cc,bcc,from_email,attachment1=None):

    email_delivery = env('EMAIL_DELIVERY', 'off')
    override_email = env('OVERRIDE_EMAIL', None)
    context['default_url'] = env('DEFAULT_URL', '')
    context['default_url_internal'] = env('DEFAULT_URL_INTERNAL', '')
    log_hash = int(hashlib.sha1(str(datetime.datetime.now()).encode('utf-8')).hexdigest(), 16) % (10 ** 8)
    if email_delivery != 'on':
        print ("EMAIL DELIVERY IS OFF NO EMAIL SENT -- applications/email.py ")
        return False

    if template is None:
        raise ValidationError('Invalid Template')
    if to is None:
        raise ValidationError('Invalid Email')
    if subject is None:
        raise ValidationError('Invalid Subject')

    if from_email is None:
        if settings.DEFAULT_FROM_EMAIL:
            from_email = settings.DEFAULT_FROM_EMAIL
        else:
            from_email = 'jason.moore@dpaw.wa.gov.au'

    context['version'] = settings.APPLICATION_VERSION_NO
    # Custom Email Body Template
    context['body'] = get_template(template).render(context)
    # Main Email Template Style ( body template is populated in the center
    main_template = get_template('email-dpaw-template.html').render(context)

    if override_email is not None:
        to = override_email.split(",")
        if cc:
            cc = override_email.split(",")
        if bcc:
            bcc = override_email.split(",")
    
    if len(to) > 1:
       for to_email in to:
          msg = EmailMessage(subject, main_template, to=[to_email],cc=cc, from_email=from_email)
          msg.content_subtype = 'html'
          if attachment1:
              msg.attach_file(attachment1)
        
          msg.send()
          print ("MESSGE")
          print (str(msg.message()))
    else:
          msg = EmailMessage(subject, main_template, to=to,cc=cc, from_email=from_email)
          msg.content_subtype = 'html'
          if attachment1:
              msg.attach_file(attachment1)
          msg.send()
          print ("MESSGE")
          print (str(msg.message()))

    if 'app' in context:
       eml_content = msg.message().as_bytes()
       #file_name = settings.BASE_DIR+"/private-media/tmp/"+str(log_hash)+".msg"
       #with open(file_name, "wb") as outfile:
       #   outfile.write(eml_content)


       #f = open(file_name, "r")
#       print(f.read())

       doc = models.Record()
       doc.upload.save(str(log_hash)+'.eml', ContentFile(eml_content), save=False)
       doc.name = str(log_hash)+'.eml' 
       doc.file_group = 2003 
       doc.file_group_ref_id = context['app'].id
       doc.extension = '.eml' 
       doc.save()
       
       
       comms = models.Communication.objects.create(application=context['app'],comms_type=2,comms_to=str(to), comms_from=from_email, subject=subject, details='see attachment')
       comms.records.add(doc)
       comms.save()
    return True

def emailGroup(subject,context,template,cc,bcc,from_email,group):

    UsersInGroup = EmailUser.objects.filter(groups__name=group)
    for person in UsersInGroup:
        context['person'] = person
        sendHtmlEmail([person.email],subject,context,template,cc,bcc,from_email)


def emailApplicationReferrals(application_id,subject,context,template,cc,bcc,from_email):

    context['default_url'] = env('DEFAULT_URL', '')
    ApplicationReferrals = Referral.objects.filter(application=application_id)
    for Referee in ApplicationReferrals:
        context['person'] = Referee.referee
        context['application_id'] = application_id
        sendHtmlEmail([Referee.referee.email],subject,context,template,cc,bcc,from_email)


