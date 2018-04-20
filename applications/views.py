from __future__ import unicode_literals
from datetime import datetime, date, timedelta
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import Group
from django.contrib.auth.tokens import default_token_generator
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import send_mail
from django.db.models import Q
from django.http import HttpResponse, HttpResponseRedirect
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.urls import reverse_lazy
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from extra_views import ModelFormSetView
from itertools import chain
import pdfkit
import re
from actions.models import Action
from applications import forms as apps_forms
from applications.models import (
    Application, Referral, Condition, Compliance, Vessel, Location, Record, PublicationNewspaper,
    PublicationWebsite, PublicationFeedback, Communication, Delegate, OrganisationContact, OrganisationPending, OrganisationExtras, CommunicationAccount,CommunicationOrganisation, ComplianceGroup,CommunicationCompliance, StakeholderComms)
from applications.workflow import Flow
from applications.views_sub import Application_Part5, Application_Emergency, Application_Permit, Application_Licence, Referrals_Next_Action_Check, FormsList
from applications.email import sendHtmlEmail, emailGroup, emailApplicationReferrals
from applications.validationchecks import Attachment_Extension_Check, is_json
from applications.utils import get_query, random_generator
from ledger.accounts.models import EmailUser, Address, Organisation, Document
from approvals.models import Approval
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import math
from django.shortcuts import redirect
from django.template import RequestContext
from django.template.loader import get_template
from statdev.context_processors import template_context 
import json
import os.path
from applications.views_pdf import PDFtool


class HomePage(TemplateView):
    # preperation to replace old homepage with screen designs..

    template_name = 'applications/home_page.html'
    def render_to_response(self, context):
       
        if self.request.user.is_authenticated:
           if len(self.request.user.first_name) > 0:
               donothing = ''
           else:
               return HttpResponseRedirect(reverse('first_login_info_steps', args=(self.request.user.id,1)))

        template = get_template(self.template_name)
        context = RequestContext(self.request, context)
        return HttpResponse(template.render(context))

    def get_context_data(self, **kwargs):
        context = super(HomePage, self).get_context_data(**kwargs)
        context = template_context(self.request)
        APP_TYPE_CHOICES = []
        APP_TYPE_CHOICES_IDS = []
 

        # mypdf = MyPDF()
        # mypdf.get_li()

        #pdftool = PDFtool()
        #pdftool.generate_part5()
        #pdftool.generate_permit()
        #pdftool.generate_section_84()
        #pdftool.generate_licence()

        context['referee'] = 'no'
        referee = Group.objects.get(name='Referee')
        if referee in self.request.user.groups.all():
            context['referee'] = 'yes'

        # Have to manually populate when using render_to_response()
        context['messages'] = messages.get_messages(self.request)
        context['request'] = self.request
        context['user'] = self.request.user

        fl = FormsList()
        if 'action' in self.kwargs:
           action = self.kwargs['action']
        else:
           action = ''
  
        if self.request.user.is_authenticated: 
            if action == '':
               context = fl.get_application(self,self.request.user.id,context)
               context['home_nav_other_applications'] = 'active'
            elif action == 'approvals':
               context = fl.get_approvals(self,self.request.user.id,context)
               context['home_nav_other_approvals'] = 'active'
            elif action == 'clearance': 
               context = fl.get_clearance(self,self.request.user.id,context)
               context['home_nav_other_clearance'] = 'active'
            elif action == 'referrals':
               context['home_nav_other_referral'] = 'active'

               if 'q' in self.request.GET and self.request.GET['q']:
                    query_str = self.request.GET['q']
                    query_str_split = query_str.split()
                    search_filter = Q()
                    for se_wo in query_str_split:
                         search_filter &= Q(pk__contains=se_wo) | Q(title__contains=se_wo)

               context['items'] = Referral.objects.filter(referee=self.request.user)

            else:
               donothing ='' 
        #for i in Application.APP_TYPE_CHOICES:
        #    if i[0] in [4,5,6,7,8,9,10,11]:
        #       skip = 'yes'
        #    else:
        #       APP_TYPE_CHOICES.append(i)
        #       APP_TYPE_CHOICES_IDS.append(i[0])
        #context['app_apptypes']= APP_TYPE_CHOICES
        #applications = Application.objects.filter(app_type__in=APP_TYPE_CHOICES_IDS)
        #print applications
        return context


class HomePageOLD(LoginRequiredMixin, TemplateView):
    # TODO: rename this view to something like UserDashboard.
    template_name = 'applications/home_page.html'

    def get_context_data(self, **kwargs):
        context = super(HomePage, self).get_context_data(**kwargs)
        if Application.objects.filter(assignee=self.request.user).exclude(state__in=[Application.APP_STATE_CHOICES.issued, Application.APP_STATE_CHOICES.declined]).exists():
            applications_wip = Application.objects.filter(
                assignee=self.request.user).exclude(state__in=[Application.APP_STATE_CHOICES.issued, Application.APP_STATE_CHOICES.declined])
            context['applications_wip'] = self.create_applist(applications_wip)
        #if Application.objects.filter(assignee=self.request.user).exclude(state__in=[Application.APP_STATE_CHOICES.issued, Application.APP_STATE_CHOICES.declined]).exists():
            #            userGroups = self.request.user.groups.all()

        userGroups = []
        for g in self.request.user.groups.all():
             userGroups.append(g.name)
             
        applications_groups = Application.objects.filter(group__name__in=userGroups).exclude(state__in=[Application.APP_STATE_CHOICES.issued, Application.APP_STATE_CHOICES.declined])
        context['applications_groups'] = self.create_applist(applications_groups)

        if Application.objects.filter(applicant=self.request.user).exists():
            applications_submitted = Application.objects.filter(
                applicant=self.request.user).exclude(assignee=self.request.user)
            context['applications_submitted'] = self.create_applist(applications_submitted)
        if Referral.objects.filter(referee=self.request.user).exists():
            context['referrals'] = Referral.objects.filter(
                referee=self.request.user, status=Referral.REFERRAL_STATUS_CHOICES.referred)

        # TODO: any restrictions on who can create new applications?
        context['may_create'] = True
        # Processor users only: show unassigned applications.
        processor = Group.objects.get(name='Processor')
        if processor in self.request.user.groups.all() or self.request.user.is_superuser:
            if Application.objects.filter(assignee__isnull=True, state=Application.APP_STATE_CHOICES.with_admin).exists():
                applications_unassigned = Application.objects.filter(
                    assignee__isnull=True, state=Application.APP_STATE_CHOICES.with_admin)
                context['applications_unassigned'] = self.create_applist(applications_unassigned)
            # Rule: admin officers may self-assign applications.
            context['may_assign_processor'] = True
        return context

    def create_applist(self, applications):
        usergroups = self.request.user.groups.all()
        app_list = []
        for app in applications:
            row = {}
            row['may_assign_to_person'] = 'False'
            row['app'] = app
            if app.group in usergroups:
                if app.group is not None:
                    row['may_assign_to_person'] = 'True'
            app_list.append(row)
        return app_list

class FirstLoginInfo(LoginRequiredMixin,CreateView):

    template_name = 'applications/firstlogin.html'
    model = EmailUser
    form_class = apps_forms.FirstLoginInfoForm

    def get(self, request, *args, **kwargs):
        return super(FirstLoginInfo, self).get(request, *args, **kwargs)

    def get_initial(self):
        initial = super(FirstLoginInfo, self).get_initial()
        #initial['action'] = self.kwargs['action']
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = self.get_object().application_set.first()
            return HttpResponseRedirect(app.get_absolute_url())
        return super(FirstLoginInfo, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        action = self.kwargs['action']
        nextstep = ''
        apply_on_behalf_of = 0
        app = Application.objects.get(pk=self.object.pk)

        return HttpResponseRedirect(success_url)

class FirstLoginInfoSteps(LoginRequiredMixin,UpdateView):

    template_name = 'applications/firstlogin.html'
    model = EmailUser
    form_class = apps_forms.FirstLoginInfoForm

    def get(self, request, *args, **kwargs):
        return super(FirstLoginInfoSteps, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(FirstLoginInfoSteps, self).get_context_data(**kwargs)
        step = self.kwargs['step']

        if step == '1':
            context['step1'] = 'active'
            context['step2'] = 'disabled'
            context['step3'] = 'disabled'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '2':
            context['step2'] = 'active'
            context['step3'] = 'disabled'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '3':
            context['step3'] = 'active'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '4':
            context['step4'] = 'active'
            context['step5'] = 'disabled'
        elif step == '5':
            context['step5'] = 'active'
        return context

    def get_initial(self):
        initial = super(FirstLoginInfoSteps, self).get_initial()
        person = self.get_object()
        # initial['action'] = self.kwargs['action']
        # print self.kwargs['step']
        step = self.kwargs['step']
        if person.identification:
            initial['identification'] = person.identification.file

        if step == '3':
            if self.object.postal_address is None:
                initial['country'] = 'AU'
                initial['state'] = 'WA'
            else: 
                postal_address = Address.objects.get(id=self.object.postal_address.id)
                initial['line1'] = postal_address.line1
                initial['line2'] = postal_address.line2
                initial['line3'] = postal_address.line3
                initial['locality'] = postal_address.locality
                initial['state'] = postal_address.state
                initial['country'] = postal_address.country
                initial['postcode'] = postal_address.postcode

        initial['step'] = self.kwargs['step']
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = self.get_object().application_set.first()
            return HttpResponseRedirect(app.get_absolute_url())
        return super(FirstLoginInfoSteps, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        step = self.kwargs['step']
        app_id = None

        if 'application_id' in self.kwargs:
            app_id = self.kwargs['application_id']

        if step == '3':
            if self.object.postal_address is None:
               postal_address = Address.objects.create(line1=forms_data['line1'],
                                        line2=forms_data['line2'],
                                        line3=forms_data['line3'],
                                        locality=forms_data['locality'],
                                        state=forms_data['state'],
                                        country=forms_data['country'],
                                        postcode=forms_data['postcode'],
                                        user=self.object
                                       )
               self.object.postal_address = postal_address
            else:
               postal_address = Address.objects.get(id=self.object.postal_address.id)
               postal_address.line1 = forms_data['line1']
               postal_address.line2 = forms_data['line2']
               postal_address.line3 = forms_data['line3']
               postal_address.locality = forms_data['locality']
               postal_address.state = forms_data['state']
               postal_address.country = forms_data['country']
               postal_address.postcode = forms_data['postcode']
               postal_address.save()

        if step == '4':
            if len(self.object.mobile_number) == 0 and len(self.object.phone_number) == 0:
                messages.error(self.request,"Please complete at least one phone number")
                if app_id is None:
                   return HttpResponseRedirect(reverse('first_login_info_steps',args=(self.object.pk, step)))
                else:
                   return HttpResponseRedirect(reverse('first_login_info_steps_application',args=(self.object.pk, step, app_id))) 

        # Upload New Files
        if self.request.FILES.get('identification'):  # Uploaded new file.
            doc = Document()
            if Attachment_Extension_Check('single', forms_data['identification'], ['.jpg','.png','.pdf']) is False:
                raise ValidationError('Identification contains and unallowed attachment extension.')

            doc.file = forms_data['identification']
            doc.name = forms_data['identification'].name
            doc.save()
            self.object.identification = doc
            
        self.object.save()
        nextstep = 1

#        action = self.kwargs['action']
        if self.request.POST.get('prev-step'):
            if step == '1':
               nextstep = 1
            elif step == '2':
               nextstep = 1
            elif step == '3':
               nextstep = 2
            elif step == '4':
               nextstep = 3
            elif step == '5':
               nextstep = 4
        else:
            if step == '1':
               nextstep = 2
            elif step == '2':
               nextstep = 3
            elif step == '3':
               nextstep = 4
            elif step == '4':
               nextstep = 5
            else:
               nextstep = 6

     
 
        if nextstep == 6:
            #print forms_data['manage_permits']
           if forms_data['manage_permits'] == 'True':
               messages.success(self.request, 'Registration is now complete. Please now complete the company form.')
               #return HttpResponseRedirect(reverse('company_create_link', args=(self.request.user.id,'1')))
               if app_id is None:
                   return HttpResponseRedirect(reverse('company_create_link', args=(self.object.pk,'1')))
               else:
                   return HttpResponseRedirect(reverse('company_create_link_application', args=(self.object.pk,'1',app_id))) 
           else:
               messages.success(self.request, 'Registration is now complete.')
               if app_id is None:
                   return HttpResponseRedirect(reverse('home_page'))
               else:
                   if self.request.user.is_staff is True:
                       app = Application.objects.get(id=app_id)
                       app.applicant = self.object
                       app.save() 
                   return HttpResponseRedirect(reverse('application_update', args=(app_id,)))
        else:
           if app_id is None:
              return HttpResponseRedirect(reverse('first_login_info_steps',args=(self.object.pk, nextstep)))
           else:
              return HttpResponseRedirect(reverse('first_login_info_steps_application',args=(self.object.pk, nextstep, app_id)))

class CreateLinkCompany(LoginRequiredMixin,CreateView):

    template_name = 'applications/companycreatelink.html'
    model = EmailUser 
    form_class = apps_forms.CreateLinkCompanyForm

    def get(self, request, *args, **kwargs):
        return super(CreateLinkCompany, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CreateLinkCompany, self).get_context_data(**kwargs)
        step = self.kwargs['step']
        context['user_id'] = self.kwargs['pk']

        if 'po_id' in self.kwargs:
            context['po_id'] = self.kwargs['po_id']
        else:
            context['po_id'] = 0

        if step == '1':
            context['step1'] = 'active'
            context['step2'] = 'disabled'
            context['step3'] = 'disabled'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '2':
            context['step2'] = 'active'
            context['step3'] = 'disabled'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '3':
            context['step3'] = 'active'
            context['step4'] = 'disabled'
            context['step5'] = 'disabled'
        elif step == '4':
            context['step4'] = 'active'
            context['step5'] = 'disabled'
        elif step == '5':
            context['step5'] = 'active'

        context['messages'] = messages.get_messages(self.request)
        return context 

    def get_initial(self):
        initial = super(CreateLinkCompany, self).get_initial()
        step = self.kwargs['step']

        initial['step'] = self.kwargs['step']
        initial['company_exists'] = ''
        pending_org = None
        if 'po_id' in self.kwargs:
            po_id = self.kwargs['po_id']
            if po_id:
                 pending_org = OrganisationPending.objects.get(id=po_id)
                 initial['company_name'] = pending_org.name
                 initial['abn'] = pending_org.abn
                 initial['pin1'] = pending_org.pin1
                 initial['pin2'] = pending_org.pin2

        if step == '2':
            if 'abn' in initial:
                abn = initial['abn']
                try:
                    if Organisation.objects.filter(abn=abn).exists():
                       company = Organisation.objects.get(abn=abn) #(abn=abn)
                       if OrganisationExtras.objects.filter(organisation=company.id).exists():
                          companyextras = OrganisationExtras.objects.get(organisation=company.id)
                          initial['company_id'] = company.id
                          initial['company_exists'] = 'yes'
                          listusers = Delegate.objects.filter(organisation__id=company.id)
                          delegate_people = ''
                          for lu in listusers:
                               if delegate_people == '':
                                   delegate_people = lu.email_user.first_name + ' '+ lu.email_user.last_name 
                               else:
                                   delegate_people = delegate_people + ', ' + lu.email_user.first_name + ' ' + lu.email_user.last_name
                          initial['company_delegates'] = delegate_people
                       else:
                          initial['company_exists'] = 'no'
                    else:
                       initial['company_exists'] = 'no' 

                except Organisation.DoesNotExist:
                    initial['company_exists'] = 'no'

#                    try: 
                        #                        companyextras = OrganisationExtras.objects.get(id=company.id)
 #                   except OrganisationExtras.DoesNotExist:
  #                      initial['company_exists'] = 'no'
            if pending_org is not None:
                if pending_org.identification:
                    initial['identification'] = pending_org.identification.upload

        if step == '3':
            if pending_org.pin1 and pending_org.pin2:
               if Organisation.objects.filter(abn=pending_org.abn).exists():
                   company = Organisation.objects.get(abn=pending_org.abn)
                   if OrganisationExtras.objects.filter(organisation=company, pin1=pending_org.pin1,pin2=pending_org.pin2).exists():
                       initial['postal_line1'] = company.postal_address.line1
                       initial['postal_line2'] = company.postal_address.line2
                       initial['postal_line3'] = company.postal_address.line3
                       initial['postal_locality'] = company.postal_address.locality
                       initial['postal_state'] = company.postal_address.state
                       initial['postal_country'] = company.postal_address.country
                       initial['postal_postcode'] = company.postal_address.postcode

                       initial['billing_line1'] = company.billing_address.line1
                       initial['billing_line2'] = company.billing_address.line2
                       initial['billing_line3'] = company.billing_address.line3
                       initial['billing_locality'] = company.billing_address.locality
                       initial['billing_state'] = company.billing_address.state
                       initial['billing_country'] = company.billing_address.country
                       initial['billing_postcode'] = company.billing_address.postcode

            else:
               if pending_org.postal_address is not None:
                   postal_address = Address.objects.get(id=pending_org.postal_address.id)
                   billing_address = Address.objects.get(id=pending_org.billing_address.id)
                   initial['postal_line1'] = postal_address.line1
                   initial['postal_line2'] = postal_address.line2
                   initial['postal_line3'] = postal_address.line3
                   initial['postal_locality'] = postal_address.locality
                   initial['postal_state'] = postal_address.state
                   initial['postal_country'] = postal_address.country
                   initial['postal_postcode'] = postal_address.postcode
               else:
                   initial['postal_state'] = 'WA'
                   initial['postal_country'] = 'AU'

               if pending_org.billing_address is not None:
                   initial['billing_line1'] = billing_address.line1
                   initial['billing_line2'] = billing_address.line2
                   initial['billing_line3'] = billing_address.line3
                   initial['billing_locality'] = billing_address.locality
                   initial['billing_state'] = billing_address.state
                   initial['billing_country'] = billing_address.country
                   initial['billing_postcode'] = billing_address.postcode
               else:
                  initial['billing_state'] = 'WA'
                  initial['billing_country'] = 'AU'

        if step == '4':
            initial['company_exists'] = 'no'
            if pending_org.pin1 and pending_org.pin2:
               if Organisation.objects.filter(abn=pending_org.abn).exists():
                    initial['company_exists'] = 'yes'


        return initial

    def post(self, request, *args, **kwargs):
        #messages.error(self.request, 'Invalid Pins ')
        #print request.path

        step = self.kwargs['step']
        if step == '2':
            company_exists = 'no'
            if 'company_exists' in request.POST:
                company_exists = request.POST['company_exists']

                if company_exists == 'yes':
                   company_id = request.POST['company_id']
    
                   pin1 = request.POST['pin1']
                   pin2 = request.POST['pin2']
                   pin1 = pin1.replace(" ", "")
                   pin2 = pin2.replace(" ", "")

                   comp = Organisation.objects.get(id=company_id)
                   if OrganisationExtras.objects.filter(organisation=comp, pin1=pin1,pin2=pin2).exists():
                       messages.success(self.request, 'Company Pins Correct')
                   else:
                       messages.error(self.request, 'Incorrect Company Pins')
                       return HttpResponseRedirect(request.path)

            else:
                if 'identification' in request.FILES:
                   if Attachment_Extension_Check('single', request.FILES['identification'], ['.pdf','.png','.jpg']) is False:
                      messages.error(self.request,'Identification contains and unallowed attachment extension.')
                      return HttpResponseRedirect(request.path)

        if request.POST.get('cancel'):
            app = self.get_object().application_set.first()
            return HttpResponseRedirect(app.get_absolute_url())
        return super(CreateLinkCompany, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        pk = self.kwargs['pk']
        step = self.kwargs['step']
        pending_org = None

        if 'po_id' in self.kwargs:
            po_id = self.kwargs['po_id']
            if po_id:
                pending_org = OrganisationPending.objects.get(id=po_id)

        if step == '1':
            abn = self.request.POST.get('abn')
            company_name = self.request.POST.get('company_name')

            if pending_org:
                pending_org.name = company_name
                pending_org.abn = abn
                pending_org.save()
            else:
                user = EmailUser.objects.get(pk=pk)
                pending_org = OrganisationPending.objects.create(name=company_name,abn=abn,email_user=user)

            action = Action(
                  content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.create,
                  action='Organisation Link/Creation Started')
            action.save()

        if step == '2':
            company_exists = forms_data['company_exists']
            if company_exists == 'yes':
                # print "COMP"
                company_id = forms_data['company_id']
                pin1 = forms_data['pin1']
                pin2 = forms_data['pin2']
                pin1 = pin1.replace(" ", "")
                pin2 = pin2.replace(" ", "")

                comp = Organisation.objects.get(id=company_id)
           
                if OrganisationExtras.objects.filter(organisation=comp, pin1=pin1,pin2=pin2).exists():
                    pending_org.pin1 = pin1
                    pending_org.pin2 = pin2
                    pending_org.company_exists = True
                    pending_org.save()

                    action = Action(
                          content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
                          action='Organisation Pins Verified')
                    action.save()

                #else:
                    #print "INCORR"

                #,id=company_id)
                # print "YESYY"
                # print forms_data['pin1']
                # print forms_data['pin2']

            else:
                if forms_data['identification']:
                   doc = Record()
                   if Attachment_Extension_Check('single', forms_data['identification'], ['.pdf','.png','.jpg']) is False:
                       raise ValidationError('Identification contains and unallowed attachment extension.')

                   doc.upload = forms_data['identification']
                   doc.name = forms_data['identification'].name
                   doc.save()
                   pending_org.identification = doc
                   pending_org.company_exists = False
                   pending_org.save()
                   action = Action(
                          content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
                          action='Identification Added')
                   action.save()


        if step == '3':
            if pending_org.postal_address is None or pending_org.billing_address is None:
                postal_address = Address.objects.create(line1=forms_data['postal_line1'],
                                                        line2=forms_data['postal_line2'],
                                                        line3=forms_data['postal_line3'],
                                                        locality=forms_data['postal_locality'],
                                                        state=forms_data['postal_state'],
                                                        country=forms_data['postal_country'],
                                                        postcode=forms_data['postal_postcode']
                        )
                billing_address = Address.objects.create(line1=forms_data['billing_line1'],
                                                        line2=forms_data['billing_line2'],
                                                        line3=forms_data['billing_line3'],
                                                        locality=forms_data['billing_locality'],
                                                        state=forms_data['billing_state'],
                                                        country=forms_data['billing_country'],
                                                        postcode=forms_data['billing_postcode']
                        )
                pending_org.postal_address = postal_address
                pending_org.billing_address = billing_address
                pending_org.save()
                action = Action(
                      content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
                      action='Address Details Added')
                action.save()

            else:
                postal_address = Address.objects.get(id=pending_org.postal_address.id)
                billing_address = Address.objects.get(id=pending_org.billing_address.id)
   
                postal_address.line1=forms_data['postal_line1']
                postal_address.line2=forms_data['postal_line2']
                postal_address.line3=forms_data['postal_line3']
                postal_address.locality=forms_data['postal_locality']
                postal_address.state=forms_data['postal_state']
                postal_address.country=forms_data['postal_country']
                postal_address.postcode=forms_data['postal_postcode']
                postal_address.save()

                billing_address.line1=forms_data['billing_line1']
                billing_address.line2=forms_data['billing_line2']
                billing_address.line3=forms_data['billing_line3']
                billing_address.locality=forms_data['billing_locality']
                billing_address.state=forms_data['billing_state']
                billing_address.country=forms_data['billing_country']
                billing_address.postcode=forms_data['postal_postcode']
                billing_address.save()

                action = Action(
                      content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
                      action='Address Details Updated')
                action.save()


            #pending_org.identification 
#            try:
#                company = Organisation.objects.get(abn=abn)
#                initial['company_exists'] = 'yes'
#            except Organisation.DoesNotExist:
#                initial['company_exists'] = 'no'
#                pending_org = OrganisationPending.objects.create(name=company_name,abn=abn)
#                print pending_org

        nextstep = 1
        if self.request.POST.get('prev-step'):
            if step == '1':
               nextstep = 1
            elif step == '2':
               nextstep = 1
            elif step == '3':
               nextstep = 2
            elif step == '4':
               nextstep = 3
            elif step == '5':
               nextstep = 4
        else:
            if step == '1':
               nextstep = 2
            elif step == '2':
               nextstep = 3
            elif step == '3':
               nextstep = 4
            elif step == '4':
               nextstep = 5
            else:
               nextstep = 6

        app_id = None
        if 'application_id' in self.kwargs:
            app_id = self.kwargs['application_id']

        if nextstep == 5:
           # print pending_org.company_exists
           if pending_org.company_exists == True: 
               pending_org.status = 2
               comp = Organisation.objects.get(abn=pending_org.abn)
               Delegate.objects.create(email_user=pending_org.email_user,organisation=comp)
               #print "Approved" 
               messages.success(self.request, 'Your company has now been linked.')
               pending_org.save()
               action = Action(
                      content_object=pending_org, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
                      action='Organisation Approved (Automatically)')
               action.save()
               OrganisationContact.objects.create(
                                                  email=pending_org.email_user.email,
                                                  first_name=pending_org.email_user.first_name,
                                                  last_name=pending_org.email_user.last_name,
                                                  phone_number=pending_org.email_user.phone_number,
                                                  mobile_number=pending_org.email_user.mobile_number,
                                                  fax_number=pending_org.email_user.fax_number,
                                                  organisation=comp
               )

           else:
              if self.request.user.is_staff is True:
                 pass 
              else:
                 messages.success(self.request, 'Your company has been submitted for approval and now pending attention by our Staff.')
                 action = Action(
                      content_object=pending_org, user=self.request.user,
                      action='Organisation is pending approval')
                 action.save()

           if self.request.user.groups.filter(name__in=['Processor']).exists():
               if app_id is None:
                   return HttpResponseRedirect(reverse('home_page'))
               else:
                   return HttpResponseRedirect(reverse('organisation_access_requests_change_applicant', args=(pending_org.id,'approve',app_id)))
        else:
           if pending_org:
              #return HttpResponseRedirect(reverse('company_create_link_steps',args=(self.request.user.id, nextstep,pending_org.id)))
              if app_id is None:
                 return HttpResponseRedirect(reverse('company_create_link_steps',args=(pk, nextstep,pending_org.id)))
              else:
                 return HttpResponseRedirect(reverse('company_create_link_steps_application',args=(pk, nextstep,pending_org.id,app_id)))
           else:
              if app_id is None:
                 return HttpResponseRedirect(reverse('company_create_link',args=(pk,nextstep)))
              else:
                 return HttpResponseRedirect(reverse('company_create_link_application',args=(pk,nextstep,app_id)))
 
        return HttpResponseRedirect(reverse('home_page'))


class ApplicationApplicantChange(LoginRequiredMixin,DetailView):

    # form_class = apps_forms.ApplicationCreateForm
    template_name = 'applications/applicant_applicantsearch.html'
    model = Application

    def get_queryset(self):
        qs = super(ApplicationApplicantChange, self).get_queryset()
        return qs

    def get_context_data(self, **kwargs):

        #listusers =  EmailUser.objects.all()
        listorgs = []
        context = super(ApplicationApplicantChange, self).get_context_data(**kwargs)
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            search_filter = Q(first_name__icontains=query_str) | Q(last_name__icontains=query_str) | Q(email__icontains=query_str)
            listusers = EmailUser.objects.filter(search_filter).exclude(is_staff=True)[:100]
        else:
            listusers =  EmailUser.objects.all().exclude(is_staff=True)[:100]

        context['acc_list'] = []
        for lu in listusers:
            row = {}
            row['acc_row'] = lu
            lu.organisations = []
            lu.organisations =  Delegate.objects.filter(email_user=lu.id) 
            context['acc_list'].append(row)
        context['applicant_id'] = self.object.pk

        return context

class ApplicationApplicantCompanyChange(LoginRequiredMixin,DetailView):

    # form_class = apps_forms.ApplicationCreateForm
    template_name = 'applications/applicant_applicant_company_search.html'
    model = Application

    def get_queryset(self):
        qs = super(ApplicationApplicantCompanyChange, self).get_queryset()
        return qs

    def get_context_data(self, **kwargs):

        listorgs = []
        context = super(ApplicationApplicantCompanyChange, self).get_context_data(**kwargs)
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            list_orgs = OrganisationExtras.objects.filter(organisation__name__icontains=query_str)
#, organisation__postal_address__icontains=query_str)
        else:
            list_orgs = OrganisationExtras.objects.all()

        context['item_list'] = []
        for lu in list_orgs:
            row = {}
            row['item_row'] = lu
            context['item_list'].append(row)
        context['company_id'] = self.object.pk

        return context

class ApplicationList(LoginRequiredMixin,ListView):
    model = Application

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        staff = context_processor['staff']
        if staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ApplicationList, self).get(request, *args, **kwargs)


    def get_queryset(self):
        qs = super(ApplicationList, self).get_queryset()

        # Did we pass in a search string? If so, filter the queryset and return
        # it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by pk, title, applicant__email, organisation__name,
            # assignee__email
            query = get_query(
                query_str, ['pk', 'title', 'applicant__email', 'organisation__name', 'assignee__email'])
            qs = qs.filter(query).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(ApplicationList, self).get_context_data(**kwargs)
        context['query_string'] = ''
        
        APP_TYPE_CHOICES = []
        APP_TYPE_CHOICES_IDS = []
        for i in Application.APP_TYPE_CHOICES:
            if i[0] in [4,5,6,7,8,9,10,11]:
               skip = 'yes'
            else:
               APP_TYPE_CHOICES.append(i)
               APP_TYPE_CHOICES_IDS.append(i[0])
        context['app_apptypes'] = APP_TYPE_CHOICES
        

        if 'action' in self.request.GET and self.request.GET['action']:
            query_str = self.request.GET['q']
            query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str) | Q(description__icontains=query_str) | Q(related_permits__icontains=query_str) | Q(jetties__icontains=query_str) | Q(drop_off_pick_up__icontains=query_str) | Q(sullage_disposal__icontains=query_str) | Q(waste_disposal__icontains=query_str) | Q(refuel_location_method__icontains=query_str) | Q(berth_location__icontains=query_str) | Q(anchorage__icontains=query_str) | Q(operating_details__icontains=query_str) | Q(proposed_development_description__icontains=query_str)

            if self.request.GET['apptype'] != '':
                query_obj &= Q(app_type=int(self.request.GET['apptype']))
            else:
                query_obj &= Q(app_type__in=APP_TYPE_CHOICES_IDS)


            if self.request.GET['applicant'] != '':
                query_obj &= Q(applicant=int(self.request.GET['applicant']))
            if self.request.GET['appstatus'] != '':
                #query_obj &= Q(state=int(self.request.GET['appstatus']))
                query_obj &= Q(route_status=self.request.GET['appstatus'])

            if 'from_date' in self.request.GET: 
                 context['from_date'] = self.request.GET['from_date']
                 context['to_date'] = self.request.GET['to_date']
                 if self.request.GET['from_date'] != '':
                     from_date_db = datetime.strptime(self.request.GET['from_date'], '%d/%m/%Y').date()
                     query_obj &= Q(submit_date__gte=from_date_db)
                 if self.request.GET['to_date'] != '':
                     to_date_db = datetime.strptime(self.request.GET['to_date'], '%d/%m/%Y').date()
                     query_obj &= Q(submit_date__lte=to_date_db)

            applications = Application.objects.filter(query_obj)
            context['query_string'] = self.request.GET['q']

            if self.request.GET['apptype'] != '':
                 context['apptype'] = int(self.request.GET['apptype'])
            if self.request.GET['applicant'] != '':
                 context['applicant'] = int(self.request.GET['applicant'])
            if 'appstatus' in self.request.GET:
                if self.request.GET['appstatus'] != '':
                    #context['appstatus'] = int(self.request.GET['appstatus'])
                    context['appstatus'] = self.request.GET['appstatus']

        else:
            to_date = datetime.today()
            from_date = datetime.today() - timedelta(days=30)
            context['from_date'] = from_date.strftime('%d/%m/%Y')
            context['to_date'] = to_date.strftime('%d/%m/%Y')
            applications = Application.objects.filter(app_type__in=APP_TYPE_CHOICES_IDS, submit_date__gte=from_date, submit_date__lte=to_date)

        context['app_applicants'] = {}
        context['app_applicants_list'] = []
#       context['app_apptypes'] = list(Application.APP_TYPE_CHOICES)
        #context['app_appstatus'] = list(Application.APP_STATE_CHOICES)
        context['app_appstatus'] = list(Application.objects.values_list('route_status',flat = True).distinct())

        usergroups = self.request.user.groups.all()
        context['app_list'] = []
        for app in applications:
            row = {}
            row['may_assign_to_person'] = 'False'
            row['app'] = app

            # Create a distinct list of applicants 
            if app.applicant:
                if app.applicant.id in context['app_applicants']:
                    donothing = ''
                else:
                    context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
                    context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name  })

            # end of creation
            if app.group is not None:
                if app.group in usergroups:
                    row['may_assign_to_person'] = 'True'
            context['app_list'].append(row)
        # TODO: any restrictions on who can create new applications?
        context['may_create'] = True
        processor = Group.objects.get(name='Processor')
        # Rule: admin officers may self-assign applications.
        if processor in self.request.user.groups.all() or self.request.user.is_superuser:
            context['may_assign_processor'] = True
        return context

class EmergencyWorksList(ListView):
    model = Application
    template_name = 'applications/emergencyworks_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        staff = context_processor['staff']
        if staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(EmergencyWorksList, self).get(request, *args, **kwargs)
   
    def get_queryset(self):
        qs = super(EmergencyWorksList, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return
        # it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by pk, title, applicant__email, organisation__name,
            # assignee__email
            query = get_query(
                query_str, ['pk', 'title', 'applicant__email', 'organisation__name', 'assignee__email'])
            qs = qs.filter(query).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(EmergencyWorksList, self).get_context_data(**kwargs)
        context['query_string'] = ''
       
        applications = Application.objects.filter(app_type=4)

        context['app_applicants'] = {}
        context['app_applicants_list'] = []
        context['app_apptypes'] = list(Application.APP_TYPE_CHOICES)

        APP_STATUS_CHOICES = []
        for i in Application.APP_STATE_CHOICES:
            if i[0] in [1,11,16]:
               APP_STATUS_CHOICES.append(i)

        context['app_appstatus'] = list(APP_STATUS_CHOICES)


        if 'action' in self.request.GET and self.request.GET['action']:
            query_str = self.request.GET['q']
            query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str)
            query_obj &= Q(app_type=4)

            if self.request.GET['applicant'] != '':
                query_obj &= Q(applicant=int(self.request.GET['applicant']))
            if self.request.GET['appstatus'] != '':
                query_obj &= Q(state=int(self.request.GET['appstatus']))


            applications = Application.objects.filter(query_obj)
            context['query_string'] = self.request.GET['q']

        if 'applicant' in self.request.GET:
            if self.request.GET['applicant'] != '':
               context['applicant'] = int(self.request.GET['applicant'])
            if 'appstatus' in self.request.GET:
               if self.request.GET['appstatus'] != '':
                  context['appstatus'] = int(self.request.GET['appstatus'])

        usergroups = self.request.user.groups.all()
        context['app_list'] = []
        for app in applications:
            row = {}
            row['may_assign_to_person'] = 'False'
            row['app'] = app

            # Create a distinct list of applicants
            if app.applicant:
                if app.applicant.id in context['app_applicants']:
                    donothing = ''
                else:
                    context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
                    context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name  })
            # end of creation

            if app.group is not None:
                if app.group in usergroups:
                    row['may_assign_to_person'] = 'True'
            context['app_list'].append(row)
        # TODO: any restrictions on who can create new applications?
        context['may_create'] = True
        processor = Group.objects.get(name='Processor')
        # Rule: admin officers may self-assign applications.
        if processor in self.request.user.groups.all() or self.request.user.is_superuser:
            context['may_assign_processor'] = True
        return context

class ComplianceList(ListView):
    model = Compliance
    template_name = 'applications/compliance_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        staff = context_processor['staff']
        if staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceList, self).get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(ComplianceList, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return
        # it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by pk, title, applicant__email, organisation__name,
            # assignee__email
            query = get_query(
                query_str, ['pk', 'title', 'applicant__email', 'assignee__email','approval_id'])
            qs = qs.filter(query).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(ComplianceList, self).get_context_data(**kwargs)
        context['query_string'] = ''

        items = ComplianceGroup.objects.filter().order_by('due_date')

        context['app_applicants'] = {}
        context['app_applicants_list'] = []
        context['app_apptypes'] = list(Application.APP_TYPE_CHOICES)

        APP_STATUS_CHOICES = []
        for i in Application.APP_STATE_CHOICES:
            if i[0] in [1,11,16]:
               APP_STATUS_CHOICES.append(i)

        context['app_appstatus'] = list(APP_STATUS_CHOICES)


        if 'action' in self.request.GET and self.request.GET['action']:
            query_str = self.request.GET['q']
            query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(assignee__email__icontains=query_str)
            query_obj &= Q(app_type=4)

            if self.request.GET['applicant'] != '':
                query_obj &= Q(applicant=int(self.request.GET['applicant']))
            if self.request.GET['appstatus'] != '':
                query_obj &= Q(state=int(self.request.GET['appstatus']))


            applications = ComplianceGroup.objects.filter(query_obj)
            context['query_string'] = self.request.GET['q']

        if 'applicant' in self.request.GET:
            if self.request.GET['applicant'] != '':
               context['applicant'] = int(self.request.GET['applicant'])
            if 'appstatus' in self.request.GET:
               if self.request.GET['appstatus'] != '':
                  context['appstatus'] = int(self.request.GET['appstatus'])



        usergroups = self.request.user.groups.all()
        context['app_list'] = []
        for item in items:
            row = {}
            row['may_assign_to_person'] = 'False'
            row['app'] = item

            # Create a distinct list of applicants
#            if app.applicant:
#                if app.applicant.id in context['app_applicants']:
#                    donothing = ''
#                else:
#                    context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
#                    context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name  })
#            # end of creation

 #            if app.group is not None:
#                if app.group in usergroups:
#                    row['may_assign_to_person'] = 'True'
#            context['app_list'].append(row)
        # TODO: any restrictions on who can create new applications?
        context['may_create'] = True
        processor = Group.objects.get(name='Processor')
        # Rule: admin officers may self-assign applications.
        if processor in self.request.user.groups.all() or self.request.user.is_superuser:
            context['may_assign_processor'] = True
        return context

class SearchMenu(ListView):
    model = Compliance
    template_name = 'applications/search_menu.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(SearchMenu, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SearchMenu, self).get_context_data(**kwargs)
        return context

class OrganisationAccessRequest(ListView):
    model = OrganisationPending
    template_name = 'applications/organisation_pending.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationAccessRequest, self).get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(OrganisationAccessRequest, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return
        # it.
        if self.request.user.groups.filter(name__in=['Processor']).exists():
           
            if 'q' in self.request.GET and self.request.GET['q']:
                query_str = self.request.GET['q']
                # Replace single-quotes with double-quotes
                query_str = query_str.replace("'", r'"')
                # Filter by pk, title, applicant__email, organisation__name,
                # assignee__email
                query = get_query(
                    query_str, ['pk'])
                qs = qs.filter(query).distinct()
                return qs

    def get_context_data(self, **kwargs):
        context = super(OrganisationAccessRequest, self).get_context_data(**kwargs)
        context['orgs_pending_status'] = OrganisationPending.STATUS_CHOICES
        context['orgs_pending_applicants'] = OrganisationPending.objects.all().values('email_user','email_user__first_name','email_user__last_name').distinct('email_user')
        query = Q()
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str = query_str.replace("'", r'"')
            query &= Q(Q(name__icontains=query_str) | Q(abn__icontains=query_str))


        if 'applicant' in self.request.GET:
            if self.request.GET['applicant'] != '':
                query  |= Q(email_user=self.request.GET['applicant'])
        if 'appstatus' in self.request.GET:
            if self.request.GET['appstatus'] != '':
                query  &= Q(status=self.request.GET['appstatus'])

        context['orgs_pending'] = OrganisationPending.objects.filter(query)[:200]


        if 'applicant' in self.request.GET:
           if self.request.GET['applicant'] != '':
               context['applicant'] = int(self.request.GET['applicant'])

        if 'appstatus' in self.request.GET:
           if self.request.GET['appstatus'] != '':
               context['appstatus'] = int(self.request.GET['appstatus'])
        context['query_string'] = ''
        if 'q' in self.request.GET and self.request.GET['q']:
            context['query_string'] = self.request.GET['q']

        return context

class OrganisationAccessRequestUpdate(LoginRequiredMixin,UpdateView):
    form_class = apps_forms.OrganisationAccessRequestForm
    model = OrganisationPending
    template_name = 'applications/organisation_pending_update.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationAccessRequestUpdate, self).get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(OrganisationAccessRequestUpdate, self).get_queryset()
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str = query_str.replace("'", r'"')
            query = get_query(
                    query_str, ['pk'])
            qs = qs.filter(query).distinct()
        return qs

    def get_initial(self):
        initial = super(OrganisationAccessRequestUpdate, self).get_initial()
        status = self.kwargs['action']
        if status == 'approve':
            initial['status'] = 2
        if status == 'decline':
            initial['status'] = 3
        return initial

    def post(self, request, *args, **kwargs):
        pk = self.kwargs['pk']
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('organisation_access_requests_view', args=(pk,) ))
        return super(OrganisationAccessRequestUpdate, self).post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationAccessRequestUpdate, self).get_context_data(**kwargs)
        return context

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        status = self.kwargs['action']
        app_id = None
        if 'application_id' in self.kwargs:
            app_id = self.kwargs['application_id']

        if status == 'approve':

        #      print self.object.name
        #      print self.object.abn
        #      print self.object.identification
        #       print self.object.postal_address
        #       print self.object.billing_address

            doc_identification = Record(id=self.object.identification.id)

            new_org = Organisation.objects.create(name=self.object.name,
                                                  abn=self.object.abn,
                                                  identification=None,
                                                  postal_address=self.object.postal_address,
                                                  billing_address=self.object.billing_address
                                                 )

            OrganisationExtras.objects.create(organisation=new_org,
                                              pin1=random_generator(),
                                              pin2=random_generator(),
                                              identification=doc_identification
                                             )


            Delegate.objects.create(email_user=self.object.email_user,organisation=new_org)
            if self.request.user.is_staff is True:
              if app_id:
                 app = Application.objects.get(id=app_id)
                 app.organisation = new_org   
                 app.save()


            # random_generator
            #OrganisationExtras.objects.create()
            self.object.status = 2
            OrganisationContact.objects.create(
                                  email=self.object.email_user.email,
                                  first_name=self.object.email_user.first_name,
                                  last_name=self.object.email_user.last_name,
                                  phone_number=self.object.email_user.phone_number,
                                  mobile_number=self.object.email_user.mobile_number,
                                  fax_number=self.object.email_user.fax_number,
                                  organisation=new_org
            )

            action = Action(
                content_object=self.object, user=self.request.user,
                action='Organisation Access Request Approved')
            action.save()
        elif status == 'decline':
            self.object.status = 3
            action = Action(
                content_object=self.object, user=self.request.user,
                action='Organisation Access Request Declined')
            action.save()

        self.object.save()
        
        if app_id is None:
            success_url = reverse('organisation_access_requests')
        else:
            success_url = reverse('application_update',args=(app_id,))

        return HttpResponseRedirect(success_url)

class OrganisationAccessRequestView(LoginRequiredMixin,DetailView):
    model = OrganisationPending
    template_name = 'applications/organisation_pending_view.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationAccessRequestView, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationAccessRequestView, self).get_context_data(**kwargs)
        app = self.get_object()
        try:
             context['org'] = Organisation.objects.get(abn=app.abn)
        except: 
             donothing = ''
#        context['conditions'] = Compliance.objects.filter(approval_id=app.id)
        return context

class SearchPersonList(ListView):
    model = Compliance
    template_name = 'applications/search_person_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(SearchPersonList, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):

        context = super(SearchPersonList, self).get_context_data(**kwargs)
        context['query_string'] = ''

        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            listorgs = Delegate.objects.filter(organisation__name__icontains=query_str)
            orgs = []
            for d in listorgs:
                d.email_user.id
                orgs.append(d.email_user.id)

            for se_wo in query_str_split:
                search_filter= Q(pk__contains=se_wo) | Q(email__icontains=se_wo) | Q(first_name__icontains=se_wo) | Q(last_name__icontains=se_wo)
            # Add Organsations Results , Will also filter out duplicates
            search_filter |= Q(pk__in=orgs)
            # Get all applicants
            listusers = EmailUser.objects.filter(search_filter).exclude(is_staff=True)[:200]
        else:
            listusers = EmailUser.objects.all().exclude(is_staff=True).order_by('-id')[:200]       

        context['acc_list'] = []
        for lu in listusers:
            row = {}
            row['acc_row'] = lu
            lu.organisations = []
            lu.organisations = Delegate.objects.filter(email_user=lu.id)
            #for o in lu.organisations:
            #    print o.organisation
            context['acc_list'].append(row)

        if 'q' in self.request.GET and self.request.GET['q']:
            context['query_string'] = self.request.GET['q']

        return context


class SearchCompanyList(ListView):
    model = Compliance
    template_name = 'applications/search_company_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(SearchCompanyList, self).get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):

        context = super(SearchCompanyList, self).get_context_data(**kwargs)
        context['query_string'] = ''

        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            #listorgs = Delegate.objects.filter(organisation__name__icontains=query_str)
            #orgs = []
            #for d in listorgs:
            #    d.email_user.id
            #    orgs.append(d.email_user.id)

            #for se_wo in query_str_split:
            #    search_filter= Q(pk__contains=se_wo) | Q(email__icontains=se_wo) | Q(first_name__icontains=se_wo) | Q(last_name__icontains=se_wo)
            # Add Organsations Results , Will also filter out duplicates
            #search_filter |= Q(pk__in=orgs)
            # Get all applicants
#            listusers = Delegate.objects.filter(organisation__name__icontains=query_str)
            listusers = OrganisationExtras.objects.filter(organisation__name__icontains=query_str)[:200]
        else:
            #            listusers = Delegate.objects.all()
            listusers = OrganisationExtras.objects.all().order_by('-id')[:200]

        context['acc_list'] = []
        for lu in listusers:
            row = {}
            # print lu.organisation.name
            row['acc_row'] = lu
#            lu.organisations = []
#            lu.organisations = Delegate.objects.filter(email_user=lu.id)
             #for o in lu.organisations:
             #    print o.organisation
            context['acc_list'].append(row)

        if 'q' in self.request.GET and self.request.GET['q']:
            context['query_string'] = self.request.GET['q']

        return context

class SearchKeywords(ListView):
    model = Compliance
    template_name = 'applications/search_keywords_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(SearchKeywords, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(SearchKeywords, self).get_context_data(**kwargs)

        context['APP_TYPES'] = Application.APP_TYPE_CHOICES
        context['query_string'] = ''

        APP_TYPE_CHOICES = [{"key":"applications", "value":"Applications"},{"key":"approvals","value":"Approvals"},{"key":"emergency","value":"Emergency Works"},{"key":"compliance","value":"Compliance"}]

        app_list_filter = []
        context['app_type_checkboxes'] = {}
        if len(self.request.GET) == 0:
            context['app_type_checkboxes'] = {'applications': 'checked', 'approvals': 'checked', 'emergency': 'checked','compliance': 'checked'}

        # print app_list_filter
        if "filter-applications" in self.request.GET:
            app_list_filter.append(1)
            app_list_filter.append(2)
            app_list_filter.append(3)
            context['app_type_checkboxes']['applications'] = 'checked'

            # print app_list_filter
        if "filter-emergency" in self.request.GET:
            app_list_filter.append(4)
            context['app_type_checkboxes']['emergency'] = 'checked'
        if "filter-approvals" in self.request.GET:
            context['app_type_checkboxes']['approvals'] = 'checked'
        if "filter-compliance" in self.request.GET:
            context['app_type_checkboxes']['compliance'] = 'checked'

            # print app_list_filter
        context['APP_TYPES'] = list(APP_TYPE_CHOICES)
        query_str_split = ''
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            search_filter_app = Q(app_type__in=app_list_filter) 
           
            # Applications: 
            for se_wo in query_str_split:
               search_filter = Q(pk__contains=se_wo)
               search_filter |= Q(title__icontains=se_wo)
               search_filter |= Q(description__icontains=se_wo)
               search_filter |= Q(related_permits__icontains=se_wo)
               search_filter |= Q(address__icontains=se_wo)
               search_filter |= Q(jetties__icontains=se_wo)
               search_filter |= Q(drop_off_pick_up__icontains=se_wo)
               search_filter |= Q(sullage_disposal__icontains=se_wo)
               search_filter |= Q(waste_disposal__icontains=se_wo)
               search_filter |= Q(refuel_location_method__icontains=se_wo)
               search_filter |= Q(berth_location__icontains=se_wo)
               search_filter |= Q(anchorage__icontains=se_wo)
               search_filter |= Q(operating_details__icontains=se_wo)
               search_filter |= Q(proposed_development_current_use_of_land__icontains=se_wo)
               search_filter |= Q(proposed_development_description__icontains=se_wo)
                
            # Add Organsations Results , Will also filter out duplicates
            # search_filter |= Q(pk__in=orgs)
            # Get all applicants
           
            apps = Application.objects.filter(search_filter_app & search_filter)

            search_filter = Q()
            for se_wo in query_str_split:
                 search_filter = Q(pk__contains=se_wo)
                 search_filter |= Q(title__icontains=se_wo)

            approvals = []
            if "filter-approvals" in self.request.GET:
                 approvals = Approval.objects.filter(search_filter)

            compliance = []
            if "filter-compliance" in self.request.GET:
                compliance = Compliance.objects.filter()


        else:
            #apps = Application.objects.filter(app_type__in=[1,2,3,4])
            #approvals = Approval.objects.all()
            apps = []
            approvals = []
            compliance = []


        context['apps_list'] = []
        for lu in apps:
            row = {}
            lu.text_found = ''
            if len(query_str_split) > 0:
              for se_wo in query_str_split:
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.title)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.related_permits)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.address)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.description)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.jetties)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.drop_off_pick_up)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.sullage_disposal)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.waste_disposal)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.refuel_location_method)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.berth_location)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.anchorage)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.operating_details)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.proposed_development_current_use_of_land)
                lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.proposed_development_description)

            if lu.app_type in [1,2,3]:
                lu.app_group = 'application'
            elif lu.app_type in [4]:
                lu.app_group = 'emergency'


            row['row'] = lu
            context['apps_list'].append(row)

        for lu in approvals:
            row = {}
            lu.text_found = ''
            if len(query_str_split) > 0:
                for se_wo in query_str_split:
                    lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.title)
            lu.app_group = 'approval'
            row['row'] = lu
            context['apps_list'].append(row)

        for lu in compliance:
            row = {}
            lu.text_found = ''
            if len(query_str_split) > 0:
                for se_wo in query_str_split:
                    lu.text_found += self.slice_keyword(" "+se_wo+" ", lu.title)
            lu.app_group = 'compliance'
            row['row'] = lu
            context['apps_list'].append(row)

        if 'q' in self.request.GET and self.request.GET['q']:
            context['query_string'] = self.request.GET['q']

        return context

    def slice_keyword(self,keyword,text_string):      

        if text_string is None:
            return ''
        if len(text_string) < 1:
            return ''
        text_string = " "+ text_string.lower() + " " 
        splitr= text_string.split(keyword.lower())
        splitr_len = len(splitr)
        text_found = ''
        loopcount = 0
        if splitr_len < 2:
           return ''
        for t in splitr:
            loopcount = loopcount + 1
            text_found += t[-20:]
            if loopcount > 1:
                if loopcount == splitr_len:
                    break
            text_found += "<b>"+keyword+"</b>"
        if len(text_found) > 2:
            text_found = text_found + '...'
        return text_found

class SearchReference(ListView):
    model = Compliance
    template_name = 'applications/search_reference_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(SearchReference, self).get(request, *args, **kwargs)

    def render_to_response(self, context):
        #    print "YESS"
        #    print context['form_prefix']
        #    print context['form_no']
        #    form = form_class(request.POST)

        if len(context['form_prefix']) > 0:
            if context['form_no'] > 0:
                if context['form_prefix'] == 'EW-' or context['form_prefix'] == 'WO-':
                    apps = Application.objects.filter(id=context['form_no'])
                    if len(apps) > 0:
                        return HttpResponseRedirect(reverse('application_detail', args=(context['form_no'],)))
                    else:
                        if context['form_prefix'] == 'EW-':
                            messages.error(self.request, 'Emergency Works does not exist.')
                        if context['form_prefix'] == 'WO-':
                            messages.error(self.request, 'Application does not exist.')

                        return HttpResponseRedirect(reverse('search_reference'))
                elif context['form_prefix'] == 'AP-':
                        approval = Approval.objects.filter(id=context['form_no'])
                        if len(approval) > 0:
                            return HttpResponseRedirect(reverse('approval_detail', args=(context['form_no'],)))
                        else:
                            messages.error(self.request, 'Approval does not exist.')

                elif context['form_prefix'] == 'CO-':
                    comp = Compliance.objects.filter(approval_id=context['form_no'])
                    if len(comp) > 0:
                        return HttpResponseRedirect(reverse('compliance_approval_detail', args=(context['form_no'],)))
                    else:
                        messages.error(self.request, 'Compliance does not exist.')

                elif context['form_prefix'] == 'AC-':
                    person = EmailUser.objects.filter(id=context['form_no'])
                    if len(person) > 0:
                        return HttpResponseRedirect(reverse('person_details_actions', args=(context['form_no'],'personal')))
                    else:
                        messages.error(self.request, 'Person account does not exist.')

                elif context['form_prefix'] == 'OG-':
                    org = Organisation.objects.filter(id=context['form_no'])
                    if len(org) > 0:
                        return HttpResponseRedirect(reverse('organisation_details_actions', args=(context['form_no'],'company')))
                    else:
                        messages.error(self.request, 'Organisation does not exist.')
                elif context['form_prefix'] == 'AR-':
                    org_pend = OrganisationPending.objects.filter(id=context['form_no'])
                    if len(org_pend) > 0:
                        return HttpResponseRedirect(reverse('organisation_access_requests_view', args=(context['form_no'])))
                    else:
                        messages.error(self.request, 'Company Access Request does not exist.')
                else:
                   messages.error(self.request, 'Invalid Prefix Provided,  Valid Prefix are EW- WO- AP- CO- AC- OG- AR-')
                   return HttpResponseRedirect(reverse('search_reference'))

            else:
                 messages.error(self.request, 'Invalid Prefix Provided,  Valid Prefix are EW- WO- AP- CO- AC- OG- AR-')
                 return HttpResponseRedirect(reverse('search_reference'))
               


#        if context['form_prefix'] == 'EW-' or context['form_prefix'] == 'WO-' or) > 0:
 #              messages.error(self.request, 'Invalid Prefix Provided,  Valid Prefix EW- WO- AP- CO-')
#               return HttpResponseRedirect(reverse('search_reference'))
        # print self
        #context['messages'] = self.messages
        template = get_template(self.template_name)
        context = RequestContext(self.request, context)
        return HttpResponse(template.render(context))

    def get_context_data(self, **kwargs):
        # def get(self, request, *args, **kwargs):
        context = {}
        # print 'test'
        context = super(SearchReference, self).get_context_data(**kwargs)
        context = template_context(self.request)
        context['messages'] = messages.get_messages(self.request)
        context['query_string'] = ''
        context['form_prefix'] = ''
        context['form_no'] = ''

        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()

            form_prefix = query_str[:3]
            form_no = query_str.replace(form_prefix,'')
            context['form_prefix'] = form_prefix
            context['form_no'] = form_no
            context['query_string'] = self.request.GET['q']

        return context

class ApplicationCreateEW(LoginRequiredMixin, CreateView):
    form_class = apps_forms.ApplicationCreateForm
    template_name = 'applications/application_form.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationAccessRequest, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationCreateEW, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new application'
        return context

    def get_form_kwargs(self):
        kwargs = super(ApplicationCreateEW, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = {}
        initial['app_type'] = 4
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(ApplicationCreateEW, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        # If this is not an Emergency Works set the applicant as current user
        if not (self.object.app_type == Application.APP_TYPE_CHOICES.emergency):
            self.object.applicant = self.request.user
        self.object.assignee = self.request.user
        self.object.submitted_by = self.request.user
        self.object.assignee = self.request.user
        self.object.submit_date = date.today()
        self.object.state = self.object.APP_STATE_CHOICES.draft
        self.object.app_type = 4
        processor = Group.objects.get(name='Processor')
        self.object.group = processor
        self.object.save()
        success_url = reverse('application_update', args=(self.object.pk,))
        return HttpResponseRedirect(success_url)

class ApplicationCreate(LoginRequiredMixin, CreateView):
    form_class = apps_forms.ApplicationCreateForm
    template_name = 'applications/application_form.html'

    def get_context_data(self, **kwargs):
        context = super(ApplicationCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new application'
        return context

    def get_form_kwargs(self):
        kwargs = super(ApplicationCreate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(ApplicationCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        # If this is not an Emergency Works set the applicant as current user
        if not (self.object.app_type == Application.APP_TYPE_CHOICES.emergency):
            self.object.applicant = self.request.user
        self.object.assignee = self.request.user
        self.object.submitted_by = self.request.user
        self.object.assignee = self.request.user
        self.object.submit_date = date.today()
        self.object.state = self.object.APP_STATE_CHOICES.new
        self.object.save()
        success_url = reverse('application_update', args=(self.object.pk,))
        return HttpResponseRedirect(success_url)

class CreateAccount(LoginRequiredMixin, CreateView):
    form_class = apps_forms.CreateAccountForm
    template_name = 'applications/create_account_form.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(CreateAccount, self).get(request, *args, **kwargs)

#    def get(self, request, *args, **kwargs):
#        #if self.request.user.groups.filter(name__in=['Processor']).exists():
#        #    app = Application.objects.create(submitted_by=self.request.user
#        #                                     ,submit_date=date.today()
#        #                                     ,state=Application.APP_STATE_CHOICES.new
#        #                                     )
#        #    return HttpResponseRedirect("/applications/"+str(app.id)+"/apply/apptype/")
#        return super(CreateAccount, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(CreateAccount, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new account'
        return context

    def get_form_kwargs(self):
        kwargs = super(CreateAccount, self).get_form_kwargs()
        #kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):

        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(CreateAccount, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        self.object.save()
        # If this is not an Emergency Works set the applicant as current user
#        success_url = reverse('first_login_info', args=(self.object.pk,1))
        app_id = None
        if 'application_id'  in self.kwargs:
            app_id = self.kwargs['application_id']
        if app_id is None:
            success_url = "/first-login/"+str(self.object.pk)+"/1/"
        else:
            success_url = "/first-login/"+str(self.object.pk)+"/1/"+str(app_id)+"/"
        return HttpResponseRedirect(success_url)

class ApplicationApply(LoginRequiredMixin, CreateView):
    form_class = apps_forms.ApplicationApplyForm
    template_name = 'applications/application_apply_form.html'

    def get(self, request, *args, **kwargs):
        if self.request.user.groups.filter(name__in=['Processor']).exists():
            app = Application.objects.create(submitted_by=self.request.user
                                             ,submit_date=date.today()
                                             ,state=Application.APP_STATE_CHOICES.new
                                             #,assignee=self.request.user
                                             )
            return HttpResponseRedirect("/applications/"+str(app.id)+"/apply/apptype/")
        return super(ApplicationApply, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationApply, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new application'
       
        return context

    def get_form_kwargs(self):
        kwargs = super(ApplicationApply, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(ApplicationApply, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data

        # If this is not an Emergency Works set the applicant as current user
        if not (self.object.app_type == Application.APP_TYPE_CHOICES.emergency):
            self.object.applicant = self.request.user
        self.object.assignee = self.request.user
        self.object.submitted_by = self.request.user
        self.object.assignee = self.request.user
        self.object.submit_date = date.today()
        self.object.state = self.object.APP_STATE_CHOICES.draft
        self.object.save()
        apply_on_behalf_of = forms_data['apply_on_behalf_of']
        if apply_on_behalf_of == '1':
            nextstep = 'apptype'
        else:
            nextstep = 'info'

        success_url = reverse('application_apply_form', args=(self.object.pk,nextstep))
        return HttpResponseRedirect(success_url)

class ApplicationApplyUpdate(LoginRequiredMixin, UpdateView):
    model = Application 
    form_class = apps_forms.ApplicationApplyUpdateForm

    def get(self, request, *args, **kwargs):
        return super(ApplicationApplyUpdate, self).get(request, *args, **kwargs)

    def get_initial(self):
        initial = super(ApplicationApplyUpdate, self).get_initial()
        initial['action'] = self.kwargs['action']
#        initial['organisations_list'] = list(i.organisation for i in Delegate.objects.filter(email_user=self.request.user))
        initial['organisations_list'] = []
        row = () 
        for i in Delegate.objects.filter(email_user=self.request.user):
            initial['organisations_list'].append((i.organisation.id,i.organisation.name))

        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = self.get_object().application_set.first()
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationApplyUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        forms_data = form.cleaned_data
        action = self.kwargs['action']
        nextstep = ''
        apply_on_behalf_of = 0
        if 'apply_on_behalf_of' in forms_data:
            apply_on_behalf_of = forms_data['apply_on_behalf_of']
        if action == 'new':
            if apply_on_behalf_of == '1':
               nextstep = 'apptype'
            else:
               nextstep = 'info'
        elif action == 'info':
            nextstep = 'apptype'
        app = Application.objects.get(pk=self.object.pk)
        if action == 'apptype':
            if self.request.user.groups.filter(name__in=['Processor']).exists():
                success_url = reverse('applicant_change', args=(self.object.pk,))
            else:
                success_url = reverse('application_update', args=(self.object.pk,))
        else:
            success_url = reverse('application_apply_form', args=(self.object.pk,nextstep))
        return HttpResponseRedirect(success_url)


class ApplicationDetail(DetailView):
    model = Application

    def get_context_data(self, **kwargs):
        context = super(ApplicationDetail, self).get_context_data(**kwargs)
        app = self.get_object()

        context['may_update'] = "False"
        context['allow_admin_side_menu'] = "False"

#       processor = Group.objects.get(name='Processor')
#       groups = Group.objects.filter(name=['Processor','Approver','Assessor','Executive'])
#       usergroups = User.objects.filter(groups__name__in=['Processor','Approver','Assessor','Executive'])
#       print self.request.user.groups.all()
#       print self.request.user.groups.filter(name__in=['Processor', 'Assessor']).exists()
#       if self.request.user.groups.all() in ['Processor']:
#       print self.request.user.groups.filter(name__in=['Processor', 'Assessor']).exists()
#       if self.request.user.groups.filter(name__in=['Processor', 'Assessor']).exists() == True:
           #             context['allow_admin_side_menu'] = "True"
#            print context['allow_admin_side_menu']
#        if groups in self.request.user.groups.all():
#            print "YES"
#        print app.app_type
#        print Application.APP_TYPE_CHOICES[app.app_type]
#        print dict(Application.APP_TYPE_CHOICES).get('3')
        # May Assign to Person,  Business rules are restricted to the people in the group who can reassign amoung each other only within the same group.
#        usergroups = self.request.user.groups.all()

#        if app.routeid > 1:
#            context['may_assign_to_person'] = 'True'
#        else:
#        context['may_assign_to_person'] = 'False'

        # if app.group is not None:
        emailcontext = {'user': 'Jason'}

        #sendHtmlEmail(['jason.moore@dpaw.wa.gov.au'],'HTML TEST EMAIL',emailcontext,'email.html' ,None,None,None)
        #emailGroup('HTML TEST EMAIL',emailcontext,'email.html' ,None,None,None,'Processor')
        if app.assignee is not None:
            context['application_assignee_id'] = app.assignee.id

        context['may_assign_to_person'] = 'False'
        usergroups = self.request.user.groups.all()
        # print app.group
        if app.group in usergroups:
            if float(app.routeid) > 1:
                context['may_assign_to_person'] = 'True'

        if app.app_type == app.APP_TYPE_CHOICES.part5:
            self.template_name = 'applications/application_details_part5_new_application.html'
            part5 = Application_Part5()
            context = part5.get(app, self, context)
        elif app.app_type == app.APP_TYPE_CHOICES.part5cr:
            self.template_name = 'applications/application_part5_ammendment_request.html'
            part5 = Application_Part5()
            context = part5.get(app, self, context)
            #flow = Flow()
            #workflowtype = flow.getWorkFlowTypeFromApp(app)
            #flow.get(workflowtype)
            #context = flow.getAccessRights(self.request,context,app.routeid,workflowtype)
            #context = flow.getCollapse(context,app.routeid,workflowtype)
            #context = flow.getHiddenAreas(context,app.routeid,workflowtype)
            #context['workflow_actions'] = flow.getAllRouteActions(app.routeid,workflowtype)
            #context['formcomponent'] = flow.getFormComponent(app.routeid,workflowtype)
        elif app.app_type == app.APP_TYPE_CHOICES.part5amend:
            self.template_name = 'applications/application_part5_amend.html'
            part5 = Application_Part5()
            context = part5.get(app, self, context)
        elif app.app_type == app.APP_TYPE_CHOICES.emergency:
            self.template_name = 'applications/application_detail_emergency.html'
            emergency = Application_Emergency()
            context = emergency.get(app, self, context)

        elif app.app_type == app.APP_TYPE_CHOICES.permit:
            permit = Application_Permit()
            context = permit.get(app, self, context)
          
        elif app.app_type == app.APP_TYPE_CHOICES.licence:
            licence = Application_Licence()
            context = licence.get(app, self, context)
        else:
            flow = Flow()
            workflowtype = flow.getWorkFlowTypeFromApp(app)
            flow.get(workflowtype)
            context = flow.getAccessRights(self.request,context,app.routeid,workflowtype)
            context = flow.getCollapse(context,app.routeid,workflowtype)
            context = flow.getHiddenAreas(context,app.routeid,workflowtype)
            context['workflow_actions'] = flow.getAllRouteActions(app.routeid,workflowtype)
            context['formcomponent'] = flow.getFormComponent(app.routeid,workflowtype)
#        print context['workflow_actions']
#        print context['allow_admin_side_menu']

        # context = flow.getAllGroupAccess(request,context,app.routeid,workflowtype)
        # may_update has extra business rules
        if float(app.routeid) > 1:
            if app.assignee is None:
                context['may_update'] = "False"
                del context['workflow_actions']
                context['workflow_actions'] = []
            if context['may_update'] == "True":
                if app.assignee != self.request.user:
                    context['may_update'] = "False"
                    del context['workflow_actions']
                    context['workflow_actions'] = []
            if app.assignee != self.request.user:
                del context['workflow_actions']
                context['workflow_actions'] = []

        context['may_update_vessels_list'] = "False"
        # elif app.app_type == app.APP_TYPE_CHOICES.emergencyold:
        #    self.template_name = 'applications/application_detail_emergency.html'
        #
        #    if app.organisation:
        #        context['address'] = app.organisation.postal_address
        #    elif app.applicant:
        #        context['address'] = app.applicant.emailuserprofile.postal_address

#        processor = Group.objects.get(name='Processor')
#        assessor = Group.objects.get(name='Assessor')
#        approver = Group.objects.get(name='Approver')
#        referee = Group.objects.get(name='Referee')
#        emergency = Group.objects.get(name='Emergency')

#        if app.state in [app.APP_STATE_CHOICES.new, app.APP_STATE_CHOICES.draft]:
            # Rule: if the application status is 'draft', it can be updated.
            # Rule: if the application status is 'draft', it can be lodged.
            # Rule: if the application is an Emergency Works and status is 'draft'
            #   conditions can be added
#            if app.app_type == app.APP_TYPE_CHOICES.emergency:
#                if app.assignee == self.request.user:
#                    context['may_update'] = True
#                    context['may_issue'] = True
#                    context['may_create_condition'] = True
#                    context['may_update_condition'] = True
#                    context['may_assign_emergency'] = True
#                elif emergency in self.request.user.groups.all() or self.request.user.is_superuser:
#                    context['may_assign_emergency'] = True
#            elif app.applicant == self.request.user or self.request.user.is_superuser:
#                context['may_update'] = True
#                context['may_lodge'] = True
#        if processor in self.request.user.groups.all() or self.request.user.is_superuser:
#            # Rule: if the application status is 'with admin', it can be sent
#            # back to the customer.
#            if app.state == app.APP_STATE_CHOICES.with_admin:
#                context['may_assign_customer'] = True
            # Rule: if the application status is 'with admin' or 'with referee', it can
            # be referred, have conditions added, and referrals can be
            # recalled/resent.
#            if app.state in [app.APP_STATE_CHOICES.with_admin, app.APP_STATE_CHOICES.with_referee]:
#                context['may_refer'] = True
#                context['may_create_condition'] = True
#                context['may_recall_resend'] = True
#                context['may_assign_processor'] = True
#                # Rule: if there are no "outstanding" referrals, it can be
#                # assigned to an assessor.
#                if not Referral.objects.filter(application=app, status=Referral.REFERRAL_STATUS_CHOICES.referred).exists():
#                    context['may_assign_assessor'] = True
#        if assessor in self.request.user.groups.all() or self.request.user.is_superuser:
#            # Rule: if the application status is 'with assessor', it can have conditions added
#            # or updated, and can be sent for approval.
#            if app.state == app.APP_STATE_CHOICES.with_assessor:
#                context['may_create_condition'] = True
#                context['may_update_condition'] = True
#                context['may_accept_condition'] = True
#                context['may_submit_approval'] = True
# if approver in self.request.user.groups.all() or self.request.user.is_superuser:
#            # Rule: if the application status is 'with manager', it can be issued or
#            # assigned back to an assessor.
#            if app.state == app.APP_STATE_CHOICES.with_manager:
#                context['may_assign_assessor'] = True
#                context['may_issue'] = True
# if referee in self.request.user.groups.all():
#            # Rule: if the application has a current referral to the request
#            # user, they can create and update conditions.
#            if Referral.objects.filter(application=app, status=Referral.REFERRAL_STATUS_CHOICES.referred).exists():
#               context['may_create_condition'] = True
#                context['may_update_condition'] = True
#        if app.state == app.APP_STATE_CHOICES.issued:
#            context['may_generate_pdf'] = True
#        if app.state == app.APP_STATE_CHOICES.issued and app.condition_set.exists():
#            # Rule: only the delegate of the organisation (or submitter) can
#            # request compliance.
#            if app.organisation:
#                if self.request.user.emailuserprofile in app.organisation.delegates.all():
#                    context['may_request_compliance'] = True
#            elif self.request.user == app.applicant:
#                context['may_request_compliance'] = True
        return context


class ApplicationDetailPDF(LoginRequiredMixin,ApplicationDetail):
    """This view is a proof of concept for synchronous, server-side PDF generation.
    Depending on performance and resource constraints, this might need to be
    refactored to use an asynchronous task.
    """
    template_name = 'applications/application_detail_pdf.html'

    def get(self, request, *args, **kwargs):
        response = super(ApplicationDetailPDF, self).get(request)
        options = {
            'page-size': 'A4',
            'encoding': 'UTF-8',
        }
        # Generate the PDF as a string, then use that as the response body.
        output = pdfkit.from_string(
            response.rendered_content, False, options=options)
        # TODO: store the generated PDF as a Record object.
        response = HttpResponse(output, content_type='application/pdf')
        obj = self.get_object()
        response['Content-Disposition'] = 'attachment; filename=application_{}.pdf'.format(
            obj.pk)
        return response

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(id=kwargs['pk'])
            if app.state == app.APP_STATE_CHOICES.new:
                app.delete()
                return HttpResponseRedirect(reverse('application_list'))
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationDetailPDF, self).post(request, *args, **kwargs)

class AccountActions(LoginRequiredMixin,DetailView):
    model = EmailUser 
    template_name = 'applications/account_actions.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(AccountActions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AccountActions, self).get_context_data(**kwargs)
        obj = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['actions'] = Action.objects.filter(
            content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk).order_by('-timestamp')
        return context

class OrganisationActions(LoginRequiredMixin,DetailView):
    model = Organisation
    template_name = 'applications/organisation_actions.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationActions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationActions, self).get_context_data(**kwargs)

        obj = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['actions'] = Action.objects.filter(
             content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk).order_by('-timestamp')
        return context

class OrganisationARActions(LoginRequiredMixin,DetailView):
    model = OrganisationPending
    template_name = 'applications/organisation_ar_actions.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationARActions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationARActions, self).get_context_data(**kwargs)

        obj = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['actions'] = Action.objects.filter(
             content_type=ContentType.objects.get_for_model(obj), object_id=obj.pk).order_by('-timestamp')
        return context

class ApplicationActions(LoginRequiredMixin,DetailView):
    model = Application
    template_name = 'applications/application_actions.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ApplicationActions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationActions, self).get_context_data(**kwargs)
        app = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['actions'] = Action.objects.filter(
            content_type=ContentType.objects.get_for_model(app), object_id=app.pk).order_by('-timestamp')
        return context

class ApplicationComms(LoginRequiredMixin,DetailView):
    model = Application 
    template_name = 'applications/application_comms.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ApplicationComms, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationComms, self).get_context_data(**kwargs)
        app = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['communications'] = Communication.objects.filter(application_id=app.pk).order_by('-created')
        return context

class ApplicationCommsCreate(LoginRequiredMixin,CreateView):
    model = Communication
    form_class = apps_forms.CommunicationCreateForm
    template_name = 'applications/application_comms_create.html'
    
    def get_context_data(self, **kwargs):
        context = super(ApplicationCommsCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new communication'
        return context

    def get_initial(self):
        initial = {}
        initial['application'] = self.kwargs['pk']
        return initial

    def get_form_kwargs(self):
        kwargs = super(ApplicationCommsCreate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('home_page'))
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationCommsCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        app_id = self.kwargs['pk']

        application = Application.objects.get(id=app_id)
        self.object.application = application
        self.object.save()

        if self.request.FILES.get('records'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents attached contains and unallowed attachment extension.')

            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)
        self.object.save()
        # If this is not an Emergency Works set the applicant as current user
        success_url = reverse('application_comms', args=(app_id,))
        return HttpResponseRedirect(success_url)

class AccountComms(LoginRequiredMixin,DetailView):
    model = EmailUser
    template_name = 'applications/account_comms.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(AccountComms, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AccountComms, self).get_context_data(**kwargs)
        u = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['communications'] = CommunicationAccount.objects.filter(user=u.pk).order_by('-created')
        return context


class AccountCommsCreate(LoginRequiredMixin,CreateView):
    model = CommunicationAccount
    form_class = apps_forms.CommunicationAccountCreateForm
    template_name = 'applications/application_comms_create.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(AccountCommsCreate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AccountCommsCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new account communication' 
        return context

    def get_initial(self):
        initial = {}
        initial['application'] = self.kwargs['pk']
        return initial

    def get_form_kwargs(self):
        kwargs = super(AccountCommsCreate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(AccountCommsCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        user_id = self.kwargs['pk']

        user = EmailUser.objects.get(id=user_id)
        self.object.user = user
        self.object.save()

        if self.request.FILES.get('records'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents attached contains and unallowed attachment extension.')

            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)
        self.object.save()
        # If this is not an Emergency Works set the applicant as current user
        success_url = reverse('account_comms', args=(user_id,))
        return HttpResponseRedirect(success_url)

class ComplianceComms(LoginRequiredMixin,DetailView):
    model = Compliance
    template_name = 'applications/compliance_comms.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceComms, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ComplianceComms, self).get_context_data(**kwargs)
        c = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['communications'] = CommunicationCompliance.objects.filter(compliance=c.pk).order_by('-created')
        return context

class ComplianceCommsCreate(LoginRequiredMixin,CreateView):
    model = CommunicationCompliance 
    form_class = apps_forms.CommunicationComplianceCreateForm
    template_name = 'applications/compliance_comms_create.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceCommsCreate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ComplianceCommsCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new account communication'
        return context

    def get_initial(self):
        initial = {}
        initial['compliance'] = self.kwargs['pk']
        return initial

    def get_form_kwargs(self):
        kwargs = super(ComplianceCommsCreate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(ComplianceCommsCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        c_id = self.kwargs['pk']

        c = Compliance.objects.get(id=c_id)
        self.object.compliance = c
        self.object.save()

        if self.request.FILES.get('records'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents attached contains and unallowed attachment extension.')
            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)
        self.object.save()
        # If this is not an Emergency Works set the applicant as current user
        success_url = reverse('compliance_comms', args=(c_id,))
        return HttpResponseRedirect(success_url)

class OrganisationComms(LoginRequiredMixin,DetailView):
    model = Organisation
    template_name = 'applications/organisation_comms.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationComms, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationComms, self).get_context_data(**kwargs)
        org = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['communications'] = CommunicationOrganisation.objects.filter(org=org.pk).order_by('-created')
        return context

class ReferralList(LoginRequiredMixin,ListView):
    model = Application
    template_name = 'applications/referral_list.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ReferralList, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralList, self).get_context_data(**kwargs)

        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            query_str_split = query_str.split()
            search_filter = Q()
            for se_wo in query_str_split:
                  search_filter &= Q(pk__contains=se_wo) | Q(title__contains=se_wo)


        context['items'] = Referral.objects.filter(referee=self.request.user)
        return context

class ReferralConditions(UpdateView):
    """A view for updating a referrals condition feedback.
    """
    model = Application
    form_class = apps_forms.ApplicationReferralConditionsPart5
    template_name = 'public/application_form.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()
        # refcount = Referral.objects.filter(referee=self.request.user).count()
        refcount = Referral.objects.filter(application=app,referee=self.request.user).count()
        if refcount == 1:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        return super(ReferralConditions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralConditions, self).get_context_data(**kwargs)
        app_id = self.kwargs['pk']
        context['page_heading'] = 'Application for new Part 5 - '+app_id
        context['left_sidebar'] = 'yes'
        #context['action'] = self.kwargs['action']
        app = self.get_object()
        return context

    def get_initial(self):
        initial = super(ReferralConditions, self).get_initial()
        app = self.get_object()

        # print self.request.user.email

        referral = Referral.objects.get(application=app,referee=self.request.user)
        #print referral.feedback

        initial['application_id'] = self.kwargs['pk']
        initial['organisation'] = app.organisation
        initial['referral_email'] = referral.referee.email
        initial['referral_name'] = referral.referee.first_name + ' ' + referral.referee.last_name

        initial['proposed_conditions'] = referral.proposed_conditions
        initial['comments'] = referral.feedback
        initial['response_date'] = referral.response_date

        multifilelist = []
        a1 = referral.records.all()
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            multifilelist.append(fileitem)

        initial['records'] = multifilelist

        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(id=kwargs['pk'])
            if app.state == app.APP_STATE_CHOICES.new:
                app.delete()
                return HttpResponseRedirect(reverse('application_list'))
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ReferralConditions, self).post(request, *args, **kwargs)


    def form_valid(self, form):
        """Override form_valid to set the state to draft is this is a new application.
        """
        forms_data = form.cleaned_data
        self.object = form.save(commit=False)
        app_id = self.kwargs['pk']
        #action = self.kwargs['action']
        status=None
       
        application = Application.objects.get(id=app_id)
        referral = Referral.objects.get(application_id=app_id,referee=self.request.user)
        referral.feedback = forms_data['comments'] 
        referral.proposed_conditions = forms_data['proposed_conditions']
        referral.response_date = date.today() 
        referral.status = Referral.REFERRAL_STATUS_CHOICES.responded

        records = referral.records.all()
        for la_co in records:
            if 'records-clear_multifileid-' + str(la_co.id) in form.data:
                referral.records.remove(la_co)

        if self.request.FILES.get('records'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents attached contains and unallowed attachment extension.')

            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                referral.records.add(doc)
        referral.save()

        refnextaction = Referrals_Next_Action_Check()
        refactionresp = refnextaction.get(application)
        if refactionresp == True:
            refnextaction.go_next_action(application)
            # Record an action.
            action = Action(
                content_object=application,
                action='No outstanding referrals, application status set to "{}"'.format(application.get_state_display()))
            action.save()

        return HttpResponseRedirect('/')

class OrganisationCommsCreate(LoginRequiredMixin,CreateView):
    model = CommunicationOrganisation
    form_class = apps_forms.CommunicationOrganisationCreateForm
    template_name = 'applications/organisation_comms_create.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(OrganisationCommsCreate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationCommsCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new organisation communication'
        context['org_id'] = self.kwargs['pk']
        return context

    def get_initial(self):
        initial = {}
        initial['org_id'] = self.kwargs['pk']
        return initial

    def get_form_kwargs(self):
        kwargs = super(OrganisationCommsCreate, self).get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('home_page'))
        return super(OrganisationCommsCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the assignee as the object creator.
        """
        self.object = form.save(commit=False)
        org_id = self.kwargs['pk']

        org = Organisation.objects.get(id=org_id)
        self.object.org_id = org.id
        self.object.save()

        if self.request.FILES.get('records'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents attached contains and unallowed attachment extension.')

            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)
        self.object.save()
        # If this is not an Emergency Works set the applicant as current user
        success_url = reverse('organisation_comms', args=(org_id,))
        return HttpResponseRedirect(success_url)


class ApplicationChange(LoginRequiredMixin, CreateView):
    """This view is for changes or ammendents to existing applications
    """
    form_class = apps_forms.ApplicationChange
    template_name = 'applications/application_change_form.html'

    def get_context_data(self, **kwargs):
        context = super(ApplicationChange, self).get_context_data(**kwargs)
        context['page_heading'] = 'Update application details'
        return context

    def get_form_kwargs(self):
         kwargs = super(ApplicationChange, self).get_form_kwargs()
         return kwargs

    def get_initial(self):
        initial = {}
        action = self.kwargs['action'] 
        approval = Approval.objects.get(id=self.kwargs['approvalid']) 
        application = Application.objects.get(id=approval.application.id)

        initial['title']  = application.title
        initial['description'] = application.description
#       initial['cost'] = application.cost

        if action == "amend": 
            if approval.ammendment_application: 
                initial['app_type'] = 6
            else:
                raise ValidationError('There was and error raising your Application Change.')
        elif action == 'requestamendment': 
            initial['app_type'] = 5
        elif action == 'renewlicence':
            initial['app_type'] = 5
        elif action == 'renewlicence':
            initial['app_type'] = 11
        elif action == 'renewpermit':
            initial['app_type'] = 10
        else:
            raise ValidationError('There was and error raising your Application Change.')

        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationChange, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the state to draft is this is a new application.
        """
        self.object = form.save(commit=False)
        action = self.kwargs['action']
        forms_data = form.cleaned_data

        approval = Approval.objects.get(id=self.kwargs['approvalid'])
        application = Application.objects.get(id=approval.application.id)

        if action == "amend":
            if approval.ammendment_application:
                self.object.app_type = 6
            else:
                raise ValidationError('There was and error raising your Application Change.')
        elif action == 'requestamendment':
                self.object.app_type = 5
        elif action == 'renewlicence':
                self.object.app_type = 11
        elif action == 'renewpermit':
                self.object.app_type = 10
        else: 
            raise ValidationError('There was and error raising your Application Change.')

        self.object.proposed_development_description = forms_data['proposed_development_description'] 
        self.object.applicant = self.request.user
        self.object.assignee = self.request.user
        self.object.submitted_by = self.request.user
        self.object.assignee = self.request.user
        self.object.submit_date = date.today()
        self.object.state = self.object.APP_STATE_CHOICES.new
        self.object.approval_id = approval.id
        self.object.save()

        if self.request.FILES.get('proposed_development_plans'):
            if Attachment_Extension_Check('multi', self.request.FILES.getlist('proposed_development_plans'), None) is False:
                raise ValidationError('Proposed Development Plans contains and unallowed attachment extension.')
        
            for f in self.request.FILES.getlist('proposed_development_plans'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.proposed_development_plans.add(doc)

#        self.object = form.save(commit=False)
        return HttpResponseRedirect(self.get_success_url())


class ApplicationConditionTable(LoginRequiredMixin, DetailView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application
    template_name = 'applications/application_conditions_table.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        context = {}

        if app.routeid is None:
            app.routeid = 1

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #if self.request.user.groups.filter(name__in=['Processor']).exists():
        #    donothing = ''
#        if context["may_update_publication_newspaper"] != "True":
#            messages.error(self.request, 'This application cannot be updated!')
#            return HttpResponseRedirect(app.get_absolute_url())

        return super(ApplicationConditionTable, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationConditionTable, self).get_context_data(**kwargs)
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        request = self.request

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()

        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        part5 = Application_Part5()
        context = part5.get(app, self, context)
        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())

class ApplicationReferTable(LoginRequiredMixin, DetailView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application
    template_name = 'applications/application_referrals_table.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        context = {}

        if app.routeid is None:
            app.routeid = 1

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #if self.request.user.groups.filter(name__in=['Processor']).exists():
        #    donothing = ''
#        if context["may_update_publication_newspaper"] != "True":
#            messages.error(self.request, 'This application cannot be updated!')
#            return HttpResponseRedirect(app.get_absolute_url())

        return super(ApplicationReferTable, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationReferTable, self).get_context_data(**kwargs)
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        request = self.request

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()

        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        part5 = Application_Part5()
        context = part5.get(app, self, context)
        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())


class ApplicationVesselTable(LoginRequiredMixin, DetailView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application
    template_name = 'applications/application_vessels_table.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        context = {}

        if app.routeid is None:
            app.routeid = 1

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #if self.request.user.groups.filter(name__in=['Processor']).exists():
        #    donothing = ''
        if context['may_update_vessels_list'] != "True":
            messages.error(self.request, 'This application cannot be updated!')
            return HttpResponseRedirect(app.get_absolute_url())

        return super(ApplicationVesselTable, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationVesselTable, self).get_context_data(**kwargs)
        #context['page_heading'] = 'Update application details'
        #context['left_sidebar'] = 'yes'
        app = self.get_object()

        # if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1
        request = self.request

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()

        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
       
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #context = flow.getCollapse(context,app.routeid,workflowtype)
        #context['workflow_actions'] = flow.getAllRouteActions(app.routeid,workflowtype)
        #context['condactions'] = flow.getAllConditionBasedRouteActions(app.routeid)
        #context['workflow'] = flow.getAllRouteConf(workflowtype,app.routeid)

        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())


class NewsPaperPublicationTable(LoginRequiredMixin, DetailView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application
    template_name = 'applications/application_publication_newspaper_table.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        context = {}

        if app.routeid is None:
            app.routeid = 1

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #if self.request.user.groups.filter(name__in=['Processor']).exists():
        #    donothing = ''
        #if context["may_update_publication_newspaper"] != "True":
        #    messages.error(self.request, 'This application cannot be updated!')
        #    return HttpResponseRedirect(app.get_absolute_url())

        return super(NewsPaperPublicationTable, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(NewsPaperPublicationTable, self).get_context_data(**kwargs)
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        request = self.request

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        part5 = Application_Part5()
        context = part5.get(app, self, context)
        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())

class FeedbackTable(LoginRequiredMixin, DetailView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application
    template_name = 'applications/application_feedback_draft_table.html'

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        context = {}
       
        if app.routeid is None:
            app.routeid = 1

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        #if self.request.user.groups.filter(name__in=['Processor']).exists():
        #    donothing = ''
#        if context["may_update_publication_newspaper"] != "True":
#            messages.error(self.request, 'This application cannot be updated!')
#            return HttpResponseRedirect(app.get_absolute_url())

        return super(FeedbackTable, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(FeedbackTable, self).get_context_data(**kwargs)
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        request = self.request

        if app.assignee:
           context['application_assignee_id'] = app.assignee.id
        else:
           context['application_assignee_id'] = None

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        context['action'] = self.kwargs['action']


        if context['action'] == 'draft':
             self.template_name = 'applications/application_feedback_draft_table.html'
        elif context['action'] == 'final':
             self.template_name = 'applications/application_feedback_final_table.html'
        elif context['action'] == 'determination':
             self.template_name = 'applications/application_feedback_determination_table.html'
         

        part5 = Application_Part5()
        context = part5.get(app, self, context)
        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())

class ApplicationUpdate(LoginRequiredMixin, UpdateView):
    """A view for updating a draft (non-lodged) application.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be changed.
        app = self.get_object()

        # Rule: if the application status is 'draft', it can be updated.
        context = {}
        if app.assignee:
            context['application_assignee_id'] = app.assignee.id
        else:
            context['application_assignee_id'] = None
#        if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1

  #      processor = Group.objects.get(name='Processor')
  #          assessor = Group.objects.get(name='Assessor')
  #          approver = Group.objects.get(name='Approver')
  #          referee = Group.objects.get(name='Referee')
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        
        if float(app.routeid) > 1:
            if app.assignee is None:
                context['may_update'] = "False"

            if context['may_update'] == "True":
                if app.assignee != self.request.user:
                    context['may_update'] = "False"

        #if context['may_update'] != "True":
        #    messages.error(self.request, 'This application cannot be updated!')
        #    return HttpResponseRedirect(app.get_absolute_url())
 #       else:
 #           if app.state != app.APP_STATE_CHOICES.draft and app.state != app.APP_STATE_CHOICES.new:
 #               messages.error(self.request, 'This application cannot be updated!')
 #               return HttpResponseRedirect(app.get_absolute_url())

        return super(ApplicationUpdate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ApplicationUpdate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Update application details'
        context['left_sidebar'] = 'yes'
        app = self.get_object()

        if app.assignee:
            context['application_assignee_id'] = app.assignee.id
        else:
            context['application_assignee_id'] = None


        # if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1
        request = self.request
        flow = Flow()
        
        workflowtype = flow.getWorkFlowTypeFromApp(app)
#        print context['workflowoptions']
        flow.get(workflowtype)
        context['workflowoptions'] = flow.getWorkflowOptions()
#        print context['workflowoptions']
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)
        context = flow.getCollapse(context,app.routeid,workflowtype)
        context['workflow_actions'] = flow.getAllRouteActions(app.routeid,workflowtype)
        context['condactions'] = flow.getAllConditionBasedRouteActions(app.routeid)
        context['workflow'] = flow.getAllRouteConf(workflowtype,app.routeid)


        if app.app_type == app.APP_TYPE_CHOICES.part5:
            part5 = Application_Part5()
            context = part5.get(app, self, context)
        elif app.app_type == app.APP_TYPE_CHOICES.part5cr:
            part5 = Application_Part5()
            context = part5.get(app, self, context)
            #flow = Flow()
            #workflowtype = flow.getWorkFlowTypeFromApp(app)
            #flow.get(workflowtype)
            #context = flow.getAccessRights(self.request,context,app.routeid,workflowtype)
            #context = flow.getCollapse(context,app.routeid,workflowtype)
            #context = flow.getHiddenAreas(context,app.routeid,workflowtype)
            #context['workflow_actions'] = flow.getAllRouteActions(app.routeid,workflowtype)
            #context['formcomponent'] = flow.getFormComponent(app.routeid,workflowtype)
        elif app.app_type == app.APP_TYPE_CHOICES.part5amend:
            part5 = Application_Part5()
            context = part5.get(app, self, context)
        elif app.app_type == app.APP_TYPE_CHOICES.emergency:
            emergency = Application_Emergency()
            context = emergency.get(app, self, context)

        elif app.app_type == app.APP_TYPE_CHOICES.permit:
            permit = Application_Permit()
            context = permit.get(app, self, context)

        elif app.app_type == app.APP_TYPE_CHOICES.licence:
            licence = Application_Licence()
            context = licence.get(app, self, context)

        try:
            LocObj = Location.objects.get(application_id=app.id)
            if LocObj:
                context['certificate_of_title_volume'] = LocObj.title_volume
                context['folio'] = LocObj.folio
                context['diagram_plan_deposit_number'] = LocObj.dpd_number
                context['location'] = LocObj.location
                context['reserve_number'] = LocObj.reserve
                context['street_number_and_name'] = LocObj.street_number_name
                context['town_suburb'] = LocObj.suburb
                context['lot'] = LocObj.lot
                context['nearest_road_intersection'] = LocObj.intersection
                context['local_government_authority'] = LocObj.local_government_authority
        except ObjectDoesNotExist:
            donothing = ''


        return context

    def get_success_url(self,app):
        return HttpResponseRedirect(app.get_absolute_url())

    def get_form_class(self):
        if self.object.app_type == self.object.APP_TYPE_CHOICES.licence:
            return apps_forms.ApplicationLicencePermitForm
        elif self.object.app_type == self.object.APP_TYPE_CHOICES.permit:
            return apps_forms.ApplicationPermitForm
        elif self.object.app_type == self.object.APP_TYPE_CHOICES.part5:
            return apps_forms.ApplicationPart5Form
        elif self.object.app_type == self.object.APP_TYPE_CHOICES.emergency:
            return apps_forms.ApplicationEmergencyForm
        elif self.object.app_type == self.object.APP_TYPE_CHOICES.permitamend:
            return apps_forms.ApplicationPermitForm
        elif self.object.app_type == self.object.APP_TYPE_CHOICES.licenceamend:
            return apps_forms.ApplicationLicencePermitForm
        else:
            # Add default forms.py and use json workflow to filter and hide fields
            return apps_forms.ApplicationPart5Form

    def get_initial(self):
        initial = super(ApplicationUpdate, self).get_initial()
        initial['application_id'] = self.kwargs['pk']

        app = self.get_object()
        initial['organisation'] = app.organisation
#        if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1

        request = self.request
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        flowcontent = {}
        if app.assignee:
            flowcontent['application_assignee_id'] = app.assignee.id
        else:
            flowcontent['application_assignee_id'] = None

        flowcontent = flow.getFields(flowcontent, app.routeid, workflowtype)
        flowcontent = flow.getAccessRights(request, flowcontent, app.routeid, workflowtype)
        flowcontent = flow.getHiddenAreas(flowcontent,app.routeid,workflowtype)
        flowcontent['condactions'] = flow.getAllConditionBasedRouteActions(app.routeid)
        initial['disabledfields'] = flow.getDisabled(flowcontent,app.routeid,workflowtype) 
        flowcontent['formcomponent'] = flow.getFormComponent(app.routeid, workflowtype)
        initial['fieldstatus'] = []

        if "fields" in flowcontent:
            initial['fieldstatus'] = flowcontent['fields']
        initial['fieldrequired'] = []
        flowcontent = flow.getRequired(flowcontent, app.routeid, workflowtype)

        if "formcomponent" in flowcontent:
            if "update" in flowcontent['formcomponent']:
                if "required" in flowcontent['formcomponent']['update']:
                    initial['fieldrequired'] = flowcontent['formcomponent']['update']['required']

        initial["workflow"] = flowcontent
        if float(app.routeid) > 1:
            if app.assignee is None:
                initial["workflow"]['may_update'] = "False"

            if initial["workflow"]['may_update'] == "True":
                if app.assignee != self.request.user:
                    initial["workflow"]['may_update'] = "False"



        initial["may_change_application_applicant"] = flowcontent["may_change_application_applicant"]
        if app.route_status == 'Draft':
            initial['sumbitter_comment'] = app.sumbitter_comment
        initial['state'] = app.state

#       flow = Flow()
        #workflow = flow.get()
#       print (workflow)
#       initial['land_owner_consent'] = app.land_owner_consent.all()

        multifilelist = []
        a1 = app.land_owner_consent.all()
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            fileitem['name'] = b1.name
            multifilelist.append(fileitem)
        initial['land_owner_consent'] = multifilelist

        a1 = app.proposed_development_plans.all()
        multifilelist = []
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            fileitem['name'] = b1.name
            multifilelist.append(fileitem)
        initial['proposed_development_plans'] = multifilelist

        a1 = app.other_relevant_documents.all()
        multifilelist = []
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            fileitem['name'] = b1.name
            multifilelist.append(fileitem)
        initial['other_relevant_documents'] = multifilelist

        a1 = app.brochures_itineries_adverts.all()
        multifilelist = []
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            fileitem['name'] = b1.name
            multifilelist.append(fileitem)
        initial['brochures_itineries_adverts'] = multifilelist

        #initial['publication_newspaper'] = PublicationNewspaper.objects.get(application_id=self.object.id)

        if app.location_route_access:
            initial['location_route_access'] = app.location_route_access
        if app.document_new_draft:
            initial['document_new_draft'] = app.document_new_draft
        if app.document_memo:
            initial['document_memo'] = app.document_memo
        if app.document_new_draft_v3:
            initial['document_new_draft_v3'] = app.document_new_draft_v3
        if app.document_draft_signed:
            initial['document_draft_signed'] = app.document_draft_signed
        if app.document_draft:
            initial['document_draft'] = app.document_draft
        if app.document_final_signed:
            initial['document_final_signed'] = app.document_final_signed
        if app.document_briefing_note:
            initial['document_briefing_note'] = app.document_briefing_note
        if app.document_determination_approved:
            initial['document_determination_approved'] = app.document_determination_approved

#       if app.proposed_development_plans:
#          initial['proposed_development_plans'] = app.proposed_development_plans.upload
        if app.deed:
            initial['deed'] = app.deed
        if app.swan_river_trust_board_feedback:
            initial['swan_river_trust_board_feedback'] = app.swan_river_trust_board_feedback
        if app.document_final:
            initial['document_final'] = app.document_final
        if app.document_determination:
            initial['document_determination'] = app.document_determination
        if app.document_completion:
            initial['document_completion'] = app.document_completion

        # Record FK fields:
        if app.cert_survey:
            initial['cert_survey'] = app.cert_survey
        if app.cert_public_liability_insurance:
            initial['cert_public_liability_insurance'] = app.cert_public_liability_insurance
        if app.risk_mgmt_plan:
            initial['risk_mgmt_plan'] = app.risk_mgmt_plan
        if app.safety_mgmt_procedures:
            initial['safety_mgmt_procedures'] = app.safety_mgmt_procedures
        if app.river_lease_scan_of_application:
            initial['river_lease_scan_of_application'] = app.river_lease_scan_of_application
        if app.supporting_info_demonstrate_compliance_trust_policies:
            initial['supporting_info_demonstrate_compliance_trust_policies'] = app.supporting_info_demonstrate_compliance_trust_policies

        try:
            LocObj = Location.objects.get(application_id=self.object.id)
            if LocObj:
                initial['certificate_of_title_volume'] = LocObj.title_volume
                initial['folio'] = LocObj.folio
                initial['diagram_plan_deposit_number'] = LocObj.dpd_number
                initial['location'] = LocObj.location
                initial['reserve_number'] = LocObj.reserve
                initial['street_number_and_name'] = LocObj.street_number_name
                initial['town_suburb'] = LocObj.suburb
                initial['lot'] = LocObj.lot
                initial['nearest_road_intersection'] = LocObj.intersection
                initial['local_government_authority'] = LocObj.local_government_authority
        except ObjectDoesNotExist:
            donothing = ''

        return initial

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        context = {}
        if app.assignee:
            context['application_assignee_id'] = app.assignee.id
        else:
            context['application_assignee_id'] = None
#        if app.app_type == app.APP_TYPE_CHOICES.part5:
#        if app.routeid is None:
#            app.routeid = 1

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(request, context, app.routeid, workflowtype)

        if float(app.routeid) > 1:
            if app.assignee is None:
                context['may_update'] = "False"

            if context['may_update'] == "True":
                if app.assignee != self.request.user:
                    context['may_update'] = "False"

        if context['may_update'] != 'True': 
           messages.error(self.request, 'You do not have permissions to update this form.')
           return HttpResponseRedirect(self.get_object().get_absolute_url())            

        if request.POST.get('cancel'):
            app = Application.objects.get(id=kwargs['pk'])
            if app.state == app.APP_STATE_CHOICES.new:
                app.delete()
                return HttpResponseRedirect(reverse('application_list'))
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the state to draft is this is a new application.
        """
        forms_data = form.cleaned_data
        self.object = form.save(commit=False)
        # ToDO remove dupes of this line below. doesn't need to be called
        # multiple times
        application = Application.objects.get(id=self.object.id)

        try:
            new_loc = Location.objects.get(application_id=self.object.id)
        except:
            new_loc = Location()
            new_loc.application_id = self.object.id

        # TODO: Potentially refactor to separate process_documents method
        # Record upload fields.
#        if 'land_owner_consent_json' in self.request.POST:
#             d = json.loads(self.request.POST['land_owner_consent_json'])
#             for i in d:
#                 print i
#                 print i['doc_id']

#        land_owner_consent = application.land_owner_consent.all()
#        for la_co in land_owner_consent:
#            if 'land_owner_consent-clear_multifileid-' + str(la_co.id) in form.data:
#                application.land_owner_consent.remove(la_co)

#        proposed_development_plans = application.proposed_development_plans.all()
#        for filelist in proposed_development_plans:
#            if 'proposed_development_plans-clear_multifileid-' + str(filelist.id) in form.data:
#                application.proposed_development_plans.remove(filelist)

#        other_relevant_documents = application.other_relevant_documents.all()
#        for filelist in other_relevant_documents:
#            if 'other_relevant_documents-clear_multifileid-' + str(filelist.id) in form.data:
#                application.other_relevant_documents.remove(filelist)

        # if 'land_owner_consent-clear_multifileid' in forms_data:
        # Check for clear checkbox (remove files)
        # Clear' was checked.
#        if 'cert_survey-clear' in form.data and self.object.cert_survey:
#            self.object.cert_survey = None
#        if 'river_lease_scan_of_application-clear' in form.data:
#            self.object.river_lease_scan_of_application = None
#        if 'cert_public_liability_insurance-clear' in form.data and self.object.cert_public_liability_insurance:
#            self.object.cert_public_liability_insurance = None
#        if 'risk_mgmt_plan-clear' in form.data and self.object.risk_mgmt_plan:
#            self.object.risk_mgmt_plan = None
#        if 'safety_mgmt_procedures-clear' in form.data and self.object.safety_mgmt_procedures:
#            self.object.safety_mgmt_procedures = None
#        if 'deed-clear' in form.data and self.object.deed:
#            self.object.deed = None
#        if 'swan_river_trust_board_feedback-clear' in form.data and self.object.swan_river_trust_board_feedback:
#            self.object.swan_river_trust_board_feedback = None
#        if 'document_new_draft_v3-clear' in form.data and self.object.document_new_draft_v3:
#            self.object.document_new_draft_v3 = None
#        if 'document_memo-clear' in form.data and self.object.document_memo:
#            self.object.document_memo = None
        #if 'document_final_signed-clear' in form.data and self.object.document_final_signed:
#            self.object.document_final_signed = None
#        if 'document_briefing_note-clear' in form.data and self.object.document_briefing_note:
 #           self.object.document_briefing_note = None
        #if 'supporting_info_demonstrate_compliance_trust_policies-clear' in form.data and self.object.supporting_info_demonstrate_compliance_trust_policies:
         #   self.object.supporting_info_demonstrate_compliance_trust_policies = None

        # Upload New Files
#        if self.request.FILES.get('cert_survey'):  # Uploaded new file.
#            if self.object.cert_survey:
#                doc = self.object.cert_survey
#            else:
#                doc = Record()
#            if Attachment_Extension_Check('single', forms_data['cert_survey'], None) is False:
#                raise ValidationError('Certficate Survey contains and unallowed attachment extension.')
#
#            doc.upload = forms_data['cert_survey']
#            doc.name = forms_data['cert_survey'].name
#            doc.save()
#            self.object.cert_survey = doc
#        if self.request.FILES.get('cert_public_liability_insurance'):
#            if self.object.cert_public_liability_insurance:
#                doc = self.object.cert_public_liability_insurance
#            else:
#                doc = Record()
#
#            if Attachment_Extension_Check('single', forms_data['cert_public_liability_insurance'], None) is False:
#                raise ValidationError('Certficate of Public Liability Insurance contains and unallowed attachment extension.')
#
#            doc.upload = forms_data['cert_public_liability_insurance']
#            doc.name = forms_data['cert_public_liability_insurance'].name
#            doc.save()
#            self.object.cert_public_liability_insurance = doc
#        if self.request.FILES.get('risk_mgmt_plan'):
#            if self.object.risk_mgmt_plan:
#                doc = self.object.risk_mgmt_plan
#            else:
#                doc = Record()
#
#            if Attachment_Extension_Check('single', forms_data['risk_mgmt_plan'], None) is False:
#                raise ValidationError('Risk Management Plan contains and unallowed attachment extension.')
#
#            doc.upload = forms_data['risk_mgmt_plan']
#            doc.name = forms_data['risk_mgmt_plan'].name
#            doc.save()
#            self.object.risk_mgmt_plan = doc
#        if self.request.FILES.get('safety_mgmt_procedures'):
#            if self.object.safety_mgmt_procedures:
#                doc = self.object.safety_mgmt_procedures
#            else:
#                doc = Record()
#            if Attachment_Extension_Check('single', forms_data['safety_mgmt_procedures'], None) is False:
#                raise ValidationError('Safety Procedures contains and unallowed attachment extension.')
#
#            doc.upload = forms_data['safety_mgmt_procedures']
#            doc.name = forms_data['safety_mgmt_procedures'].name
#            doc.save()
#            self.object.safety_mgmt_procedures = doc
        
        # if self.request.FILES.get('deed'):
        #    if self.object.deed:
        #        doc = self.object.deed
        #    else:
        #        doc = Record()
#
#            if Attachment_Extension_Check('single',forms_data['deed'],None) is False:
 #               raise ValidationError('Deed contains and unallowed attachment extension.')
#
 #           doc.upload = forms_data['deed']
  #          doc.name = forms_data['deed'].name
   #         doc.save()
    #        self.object.deed = doc
#        if self.request.FILES.get('river_lease_scan_of_application'):
#            if self.object.river_lease_scan_of_application:
#                doc = self.object.river_lease_scan_of_application
#            else:
#                doc = Record()
#            if Attachment_Extension_Check('single',forms_data['river_lease_scan_of_application'],None) is False:
#                raise ValidationError('River Lease contains an unallowed attachment extension.')
#
#            doc.upload = forms_data['river_lease_scan_of_application']
#            doc.name = forms_data['river_lease_scan_of_application'].name
#            doc.save()
#            self.object.river_lease_scan_of_application = doc

#        if self.request.FILES.get('other_relevant_documents'):
            # Remove existing documents.
 #           for d in self.object.other_relevant_documents.all():
  #              self.object.other_relevant_documents.remove(d)
            # Add new uploads.
#            if Attachment_Extension_Check('multi', self.request.FILES.getlist('other_relevant_documents'), None) is False:
#                raise ValidationError('Other relevant documents contains and unallowed attachment extension.')
#
#            for f in self.request.FILES.getlist('other_relevant_documents'):
#                doc = Record()
#                doc.upload = f
#                doc.name = f.name
#                doc.save()
#                self.object.other_relevant_documents.add(doc)

#        brochures_itineries_adverts = application.brochures_itineries_adverts.all()
#        for filelist in brochures_itineries_adverts:
#            if 'brochures_itineries_adverts-clear_multifileid-' + str(filelist.id) in form.data:
#                 self.object.brochures_itineries_adverts.remove(filelist)


#        if self.request.FILES.get('brochures_itineries_adverts'):
            #  print self.request.FILES.getlist('brochures_itineries_adverts')
            # Remove existing documents.
#            for d in self.object.brochures_itineries_adverts.all():
 #               self.object.brochures_itineries_adverts.remove(d)
            # Add new uploads.
 #           if Attachment_Extension_Check('multi', self.request.FILES.getlist('brochures_itineries_adverts'), None) is False:
 #               raise ValidationError('Brochures Itineries contains and unallowed attachment extension.')
#
#            for f in self.request.FILES.getlist('brochures_itineries_adverts'):
#                doc = Record()
#                doc.upload = f
#                doc.name = f.name
#                doc.save()
#                self.object.brochures_itineries_adverts.add(doc)

#        if self.request.FILES.get('land_owner_consent'):
            # Remove existing documents.
            # for d in self.object.land_owner_consent.all():
            #    self.object.land_owner_consent.remove(d)
            # Add new uploads.
#            if Attachment_Extension_Check('multi', self.request.FILES.getlist('land_owner_consent'), None) is False:
#                raise ValidationError('Land Owner Consent contains and unallowed attachment extension.')
#
#            for f in self.request.FILES.getlist('land_owner_consent'):
#                doc = Record()
 #               doc.upload = f
       #         doc.name = f.name
 ##               doc.save()
 #               self.object.land_owner_consent.add(doc)

        if 'other_relevant_documents_json' in self.request.POST:
             json_data = json.loads(self.request.POST['other_relevant_documents_json'])
             for d in self.object.other_relevant_documents.all():
                 self.object.other_relevant_documents.remove(d)
             for i in json_data:
                 doc = Record.objects.get(id=i['doc_id'])
                 self.object.other_relevant_documents.add(doc)

        if 'brochures_itineries_adverts_json' in self.request.POST:
             if is_json(self.request.POST['brochures_itineries_adverts_json']) is True:
                 json_data = json.loads(self.request.POST['brochures_itineries_adverts_json'])
                 for d in self.object.brochures_itineries_adverts.all():
                    self.object.brochures_itineries_adverts.remove(d)
                 for i in json_data:
                    doc = Record.objects.get(id=i['doc_id'])
                    self.object.brochures_itineries_adverts.add(doc)

        if 'land_owner_consent_json' in self.request.POST:
             if is_json(self.request.POST['land_owner_consent_json']) is True:
                 json_data = json.loads(self.request.POST['land_owner_consent_json'])
                 for d in self.object.land_owner_consent.all():
                     self.object.land_owner_consent.remove(d)
                 for i in json_data:
                     doc = Record.objects.get(id=i['doc_id'])
                     self.object.land_owner_consent.add(doc)

        if 'proposed_development_plans_json' in self.request.POST:
             json_data = json.loads(self.request.POST['proposed_development_plans_json'])
             self.object.proposed_development_plans.remove()
             for d in self.object.proposed_development_plans.all():
                 self.object.proposed_development_plans.remove(d)
             for i in json_data:
                 doc = Record.objects.get(id=i['doc_id'])
                 self.object.proposed_development_plans.add(doc)

        if 'document_draft_json' in self.request.POST:
           self.object.document_draft = None
           if is_json(self.request.POST['document_draft_json']) is True:
                json_data = json.loads(self.request.POST['document_draft_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_draft = new_doc

        if 'river_lease_scan_of_application_json' in self.request.POST:
           if is_json(self.request.POST['river_lease_scan_of_application_json']) is True:
                json_data = json.loads(self.request.POST['river_lease_scan_of_application_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.river_lease_scan_of_application = new_doc


#        if 'document_draft_json' in self.request.POST:
 #            json_data = json.loads(self.request.POST['document_draft_json'])
 #            for i in json_data:
 #                doc = Record.objects.get(id=i['doc_id'])
  #               self.object.proposed_development_plans.add(doc)


#        if self.request.FILES.get('proposed_development_plans'):
#            if Attachment_Extension_Check('multi', self.request.FILES.getlist('proposed_development_plans'), None) is False:
#                raise ValidationError('Proposed Development Plans contains and unallowed attachment extension.')
#
#            for f in self.request.FILES.getlist('proposed_development_plans'):
#                doc = Record()
#                doc.upload = f
#                doc.save()
#                self.object.proposed_development_plans.add(doc)

#        if self.request.POST.get('document_draft-clear'):
            #application = Application.objects.get(id=self.object.id)
            #document = Record.objects.get(pk=application.document_draft.id)
            # document.delete() // protect error occurs
#            self.object.document_draft = None

 #       if self.request.POST.get('document_new_draft-clear'):
            #application = Application.objects.get(id=self.object.id)
#            self.object.document_new_draft = None

#        if self.request.POST.get('document_draft_signed-clear'):
#            self.object.document_draft_signed = None

#        if self.request.POST.get('document_determination_approved-clear'):
#            self.object.document_determination_approved = None

#        if self.request.FILES.get('document_draft'):
#            if Attachment_Extension_Check('single', forms_data['document_draft'], None) is False:
#                raise ValidationError('Draft contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_draft']
#            new_doc.save()
#            self.object.document_draft = new_doc

#        if self.request.FILES.get('document_new_draft'):
#            if Attachment_Extension_Check('single', forms_data['document_new_draft'], None) is False:
#                raise ValidationError('New Draft contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_new_draft']
#            new_doc.save()
#            self.object.document_new_draft = new_doc

#        if self.request.FILES.get('document_new_draft_v3'):
#            if Attachment_Extension_Check('single', forms_data['document_new_draft_v3'], None) is False:
#                raise ValidationError('Draft V3 contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_new_draft_v3']
#            new_doc.save()
#            self.object.document_new_draft_v3 = new_doc

#       if self.request.FILES.get('document_memo'):
#            if Attachment_Extension_Check('single', forms_data['document_memo'], None) is False:
#                raise ValidationError('Memo contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_memo']
#            new_doc.save()
#            self.object.document_memo = new_doc

#       if self.request.FILES.get('document_draft_signed'):
#            if Attachment_Extension_Check('single', forms_data['document_draft_signed'], None) is False:
#                raise ValidationError('New Draft contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_draft_signed']
#            new_doc.save()
#            self.object.document_draft_signed = new_doc

#        if self.request.FILES.get('document_final'):
#            if Attachment_Extension_Check('single', forms_data['document_final'], None) is False:
#               raise ValidationError('Final contains and unallowed attachment extension.')

#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_final']
#            new_doc.save()
#            self.object.document_final = new_doc

#        if self.request.FILES.get('document_final_signed'):
#            if Attachment_Extension_Check('single', forms_data['document_final_signed'], None) is False:
#                raise ValidationError('Final Signed contains and unallowed attachment extension.')
##            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_final_signed']
#            new_doc.save()
#            self.object.document_final_signed = new_doc

        #if self.request.FILES.get('swan_river_trust_board_feedback'):
        #    if Attachment_Extension_Check('single', forms_data['swan_river_trust_board_feedback'], None) is False:
        #        raise ValidationError('Swan River Trust Board Feedback contains and unallowed attachment extension.')
#
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['swan_river_trust_board_feedback']
#            new_doc.save()
#            self.object.swan_river_trust_board_feedback = new_doc

#        if self.request.FILES.get('deed'):
#            if Attachment_Extension_Check('single', forms_data['deed'], None) is False:
#                raise ValidationError('Deed contains and unallowed attachment extension.')
#
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['deed']
#            new_doc.save()
#            self.object.deed = new_doc

        if 'document_final_json' in self.request.POST:
           self.object.document_final = None
           if is_json(self.request.POST['document_final_json']) is True:
                json_data = json.loads(self.request.POST['document_final_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_final = new_doc

        if 'location_route_access_json' in self.request.POST:
           self.object.location_route_access = None
           if is_json(self.request.POST['location_route_access_json']) is True:
                json_data = json.loads(self.request.POST['location_route_access_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.location_route_access = new_doc

        if 'safety_mgmt_procedures_json' in self.request.POST:
           self.object.safety_mgmt_procedures = None
           if is_json(self.request.POST['safety_mgmt_procedures_json']) is True:
                json_data = json.loads(self.request.POST['safety_mgmt_procedures_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.safety_mgmt_procedures = new_doc

        if 'risk_mgmt_plan_json' in self.request.POST:
           self.object.risk_mgmt_plan = None
           if is_json(self.request.POST['risk_mgmt_plan_json']) is True:
                json_data = json.loads(self.request.POST['risk_mgmt_plan_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.risk_mgmt_plan = new_doc

        if 'cert_public_liability_insurance_json' in self.request.POST:
           self.object.cert_public_liability_insurance = None
           if is_json(self.request.POST['cert_public_liability_insurance_json']) is True:
                json_data = json.loads(self.request.POST['cert_public_liability_insurance_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.cert_public_liability_insurance = new_doc

        if 'cert_survey_json' in self.request.POST:
           self.object.cert_survey = None
           if is_json(self.request.POST['cert_survey_json']) is True:
                json_data = json.loads(self.request.POST['cert_survey_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.cert_survey = new_doc

        if 'supporting_info_demonstrate_compliance_trust_policies_json' in self.request.POST:
           self.object.supporting_info_demonstrate_compliance_trust_policies = None
           if is_json(self.request.POST['supporting_info_demonstrate_compliance_trust_policies_json']) is True:
                json_data = json.loads(self.request.POST['supporting_info_demonstrate_compliance_trust_policies_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.supporting_info_demonstrate_compliance_trust_policies = new_doc

        if 'document_determination_approved_json' in self.request.POST:
           self.object.document_determination_approved = None
           if is_json(self.request.POST['document_determination_approved_json']) is True:
                json_data = json.loads(self.request.POST['document_determination_approved_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_determination_approved = new_doc

        if 'document_determination_json' in self.request.POST:
           self.object.document_determination = None
           if is_json(self.request.POST['document_determination_json']) is True:
                json_data = json.loads(self.request.POST['document_determination_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_determination = new_doc

        if 'document_briefing_note_json' in self.request.POST:
           self.object.document_briefing_note = None
           if is_json(self.request.POST['document_briefing_note_json']) is True:
                json_data = json.loads(self.request.POST['document_briefing_note_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_briefing_note = new_doc

        if 'document_briefing_note_json' in self.request.POST:
           self.object.document_briefing_note = None
           if is_json(self.request.POST['document_briefing_note_json']) is True:
                json_data = json.loads(self.request.POST['document_briefing_note_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_briefing_note = new_doc

        if 'document_new_draft_v3_json' in self.request.POST:
           self.object.document_new_draft_v3 = None
           if is_json(self.request.POST['document_new_draft_v3_json']) is True:
                json_data = json.loads(self.request.POST['document_new_draft_v3_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_new_draft_v3 = new_doc


        if 'document_memo_json' in self.request.POST:
           self.object.document_memo = None
           if is_json(self.request.POST['document_memo_json']) is True:
                json_data = json.loads(self.request.POST['document_memo_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_memo = new_doc

        if 'deed_json' in self.request.POST:
           self.object.deed = None
           if is_json(self.request.POST['deed_json']) is True:
                json_data = json.loads(self.request.POST['deed_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.deed = new_doc
        
        if 'swan_river_trust_board_feedback_json' in self.request.POST:
           self.object.swan_river_trust_board_feedback = None
           if is_json(self.request.POST['swan_river_trust_board_feedback_json']) is True:
                json_data = json.loads(self.request.POST['swan_river_trust_board_feedback_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.swan_river_trust_board_feedback = new_doc


        if 'river_lease_scan_of_application_json' in self.request.POST:
           self.object.river_lease_scan_of_application = None
           if is_json(self.request.POST['river_lease_scan_of_application_json']) is True:
                json_data = json.loads(self.request.POST['river_lease_scan_of_application_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.river_lease_scan_of_application = new_doc

        if 'document_draft_signed_json' in self.request.POST:
           self.object.document_draft_signed = None
           if is_json(self.request.POST['document_draft_signed_json']) is True:
                json_data = json.loads(self.request.POST['document_draft_signed_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_draft_signed = new_doc

        if 'document_final_signed_json' in self.request.POST:
           self.object.document_final_signed = None
           if is_json(self.request.POST['document_final_signed_json']) is True:
                json_data = json.loads(self.request.POST['document_final_signed_json'])
                new_doc = Record.objects.get(id=json_data['doc_id'])
                self.object.document_final_signed = new_doc


# document_final_signed
                #    if Attachment_Extension_Check('single', forms_data['river_lease_scan_of_application'], None) is False:
                #        raise ValidationError('River Lease Scan of Application contains and unallowed attachment extension.')

#            new_doc = Record()
#            new_doc.upload = self.request.FILES['river_lease_scan_of_application']
#            new_doc.save()
#            self.object.river_lease_scan_of_application = new_doc
        if self.request.FILES.get('document_determination'):
            if Attachment_Extension_Check('single', forms_data['document_determination'], None) is False:
                raise ValidationError('Determination contains and unallowed attachment extension.')

            new_doc = Record()
            new_doc.upload = self.request.FILES['document_determination']
            new_doc.save()
            self.object.document_determination = new_doc

#        if self.request.FILES.get('document_determination_approved'):
#            if Attachment_Extension_Check('single', forms_data['document_determination_approved'], None) is False:
#                raise ValidationError('Determination contains and unallowed attachment extension.')
#            new_doc = Record()
#            new_doc.upload = self.request.FILES['document_determination_approved']
#            new_doc.save()
#            self.object.document_determination_approved = new_doc

        if self.request.FILES.get('document_briefing_note'):
            if Attachment_Extension_Check('single', forms_data['document_briefing_note'], None) is False:
                raise ValidationError('Briefing Note contains and unallowed attachment extension.')

            new_doc = Record()
            new_doc.upload = self.request.FILES['document_briefing_note']
            new_doc.save()
            self.object.document_briefing_note = new_doc

        if self.request.FILES.get('document_completion'):
            if Attachment_Extension_Check('single', forms_data['document_completion'], None) is False:
                raise ValidationError('Completion Docuemnt contains and unallowed attachment extension.')

            new_doc = Record()
            new_doc.upload = self.request.FILES['document_completion']
            new_doc.save()
            self.object.document_completion = new_doc

        #if self.request.FILES.get('supporting_info_demonstrate_compliance_trust_policies'):
        #    if Attachment_Extension_Check('single', forms_data['supporting_info_demonstrate_compliance_trust_policies'], None) is False:
        #        raise ValidationError('Completion Docuemnt contains and unallowed attachment extension.')
        #    new_doc = Record()
        #    new_doc.upload = self.request.FILES['supporting_info_demonstrate_compliance_trust_policies']
        #    new_doc.save()
        #    self.object.supporting_info_demonstrate_compliance_trust_policies = new_doc
        #
        #new_loc.title_volume = forms_data['certificate_of_title_volume']

        if 'certificate_of_title_volume' in forms_data:
            new_loc.title_volume = forms_data['certificate_of_title_volume']
        if 'folio' in forms_data:
            new_loc.folio = forms_data['folio']
        if 'diagram_plan_deposit_number' in forms_data:
            new_loc.dpd_number = forms_data['diagram_plan_deposit_number']
        if 'location' in forms_data:
            new_loc.location = forms_data['location']
        if 'reserve_number' in forms_data:
            new_loc.reserve = forms_data['reserve_number']
        if 'street_number_and_name' in forms_data:
            new_loc.street_number_name = forms_data['street_number_and_name']
        if 'town_suburb' in forms_data:
            new_loc.suburb = forms_data['town_suburb']
        if 'lot' in forms_data:
            new_loc.lot = forms_data['lot']
        if 'nearest_road_intersection' in forms_data:
            new_loc.intersection = forms_data['nearest_road_intersection']
        if 'local_government_authority' in forms_data:
            new_loc.local_government_authority = forms_data['local_government_authority']

        if self.object.state == Application.APP_STATE_CHOICES.new:
            self.object.state = Application.APP_STATE_CHOICES.draft

        if self.object.jetty_dot_approval is None:
             self.object.jetty_dot_approval = None 
        if self.object.vessel_or_craft_details == '':
             self.object.vessel_or_craft_details =None
        if self.object.beverage == '':
             self.object.beverage = None
        if self.object.byo_alcohol == '':
             self.object.byo_alcohol = None
        if self.object.liquor_licence == '':
             self.object.liquor_licence = None        

        self.object.save()
        new_loc.save()

        if self.object.app_type == self.object.APP_TYPE_CHOICES.licence:
            form.save_m2m()
#        if self.request.POST.get('save'):
#        if self.request.POST.get('nextstep') or self.request.POST.get('prevstep'):
            # print self.request.POST['nextstep']          
            # if self.request.POST.get('prevstep'):
            # print self.request.POST['nextstep']
            # print "CONDITION ROUTING"
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(application)
        flow.get(workflowtype)
        conditionactions = flow.getAllConditionBasedRouteActions(application.routeid)
        if conditionactions:
             for ca in conditionactions:
                 for fe in self.request.POST:
                     if ca == fe:
                         for ro in conditionactions[ca]['routeoptions']:
                             if ro['field'] in self.request.POST:
                                 if ro['fieldvalue'] == self.request.POST[ro['field']]:
                                     if "routeurl" in ro:
                                        if ro["routeurl"] == "application_lodge":
                                            return HttpResponseRedirect(reverse(ro["routeurl"],kwargs={'pk':self.object.id}))
                                        if ro["routeurl"] == "application_issue":
                                            return HttpResponseRedirect(reverse(ro["routeurl"],kwargs={'pk':self.object.id}))

                                     self.object.routeid = ro['route']
                                     self.object.state = ro['state']
                                     self.object.route_status = flow.json_obj[ro['route']]['title']
                                     self.object.save()

                                     routeurl = "application_update" 
                                     if "routeurl" in ro:
                                         routeurl = ro["routeurl"]
                                     return HttpResponseRedirect(reverse(routeurl,kwargs={'pk':self.object.id}))
        self.object.save()
        return HttpResponseRedirect(self.object.get_absolute_url()+'update/')
        #return HttpResponseRedirect(self.get_success_url(self.object))

class ApplicationLodge(LoginRequiredMixin, UpdateView):
    model = Application
    form_class = apps_forms.ApplicationLodgeForm
    template_name = 'applications/application_lodge.html'

    def get_context_data(self, **kwargs):
        context = super(ApplicationLodge, self).get_context_data(**kwargs)
        app = self.get_object()

        if app.app_type == app.APP_TYPE_CHOICES.part5:
            self.template_name = 'applications/application_lodge_part5.html'
        if app.routeid is None:
            app.routeid = 1
        return context

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be lodged.
        # Rule: application state must be 'draft'.
        app = self.get_object()
        flowcontext = {}
        error_messages = False 

        if app.assignee: 
            flowcontext['application_assignee_id'] = app.assignee.id
        else:
            flowcontext['application_assignee_id'] = None

        workflowtype = ''

        if app.routeid is None:
            app.routeid = 1
        request = self.request
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext['may_lodge'] == "True":
            route = flow.getNextRouteObj('lodge', app.routeid, workflowtype)
            flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)

            if route is not None: 
                if 'required' in route:
                    for fielditem in route["required"]:
                         if hasattr(app, fielditem):
                            if getattr(app, fielditem) is None:
                                messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                                error_messages = True
                                #return HttpResponseRedirect(app.get_absolute_url()+'update/')
                            appattr = getattr(app, fielditem)
                            if isinstance(appattr, unicode) or isinstance(appattr, str):
                                if len(appattr) == 0:
                                    messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                                    error_messages = True
                    if error_messages is True:
                        return HttpResponseRedirect(app.get_absolute_url()+'update/')
                    donothing = ""
            else:
                messages.error(self.request, 'This application has no matching routes.')
                return HttpResponseRedirect(app.get_absolute_url())
        else:
            messages.error(self.request, 'This application cannot be lodged!')
            return HttpResponseRedirect(app.get_absolute_url())

        return super(ApplicationLodge, self).get(request, *args, **kwargs)

    def get_success_url(self):
        #return reverse('application_list')
        return reverse('home_page')

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            #return HttpResponseRedirect(self.get_object().get_absolute_url())
            return HttpResponseRedirect(self.get_object().get_absolute_url()+'update/')
        return super(ApplicationLodge, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override form_valid to set the submit_date and status of the new application.
        """
        app = self.get_object()
        flowcontext = {}
        error_messages = False
        # if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        nextroute = flow.getNextRoute('lodge', app.routeid, workflowtype)
        route = flow.getNextRouteObj('lodge', app.routeid, workflowtype)
       
        app.routeid = nextroute
        flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)
        if "required" in route:
            for fielditem in route["required"]:
                if hasattr(app, fielditem):
                    if getattr(app, fielditem) is None:
                        messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                        error_messages = True
                        #return HttpResponseRedirect(app.get_absolute_url()+'update/')
                    appattr = getattr(app, fielditem)
                    if isinstance(appattr, unicode) or isinstance(appattr, str):
                        if len(appattr) == 0:
                            messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                            error_messages = True
            if error_messages is True:
                 return HttpResponseRedirect(app.get_absolute_url()+'update/')

        groupassignment = Group.objects.get(name=DefaultGroups['grouplink']['admin'])
        app.group = groupassignment

        app.state = app.APP_STATE_CHOICES.with_admin
        self.object.submit_date = date.today()
        app.assignee = None
        app.save()

        # this get uses the new route id to get title of new route and updates the route_status.
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        app.route_status = flow.json_obj[app.routeid]['title']
        app.save()


        # Generate a 'lodge' action:
        action = Action(
            content_object=app, category=Action.ACTION_CATEGORY_CHOICES.lodge,
            user=self.request.user, action='Application lodgement')
        action.save()
        # Success message.
        msg = """Your {0} application has been successfully submitted. The application
        number is: <strong>WO-{1}</strong>.<br>
        Please note that routine applications take approximately 4-6 weeks to process.<br>
        If any information is unclear or missing, Parks and Wildlife may return your
        application to you to amend or complete.<br>
        The assessment process includes a 21-day external referral period. During this time
        your application may be referred to external departments, local government
        agencies or other stakeholders. Following this period, an internal report will be
        produced by an officer for approval by the Manager, Rivers and Estuaries Division,
        to determine the outcome of your application.<br>
        You will be notified by email once your {0} application has been determined and/or
        further action is required.""".format(app.get_app_type_display(), app.pk)
        messages.success(self.request, msg)


        emailcontext = {}
        emailcontext['app'] = self.object

        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
        emailcontext['person'] = app.submitted_by
        emailcontext['body'] = msg 
        sendHtmlEmail([app.submitted_by.email], emailcontext['application_name'] + ' application submitted ', emailcontext, 'application-lodged.html', None, None, None)

        return HttpResponseRedirect(self.get_success_url())


class ApplicationRefer(LoginRequiredMixin, CreateView):
    """A view to create a Referral object on an Application (if allowed).
    """
    model = Referral
    form_class = apps_forms.ReferralForm

    def get(self, request, *args, **kwargs):
        # TODO: business logic to check the application may be referred.
        # Rule: application state must be 'with admin' or 'with referee'
        app = Application.objects.get(pk=self.kwargs['pk'])

        flowcontext = {}
      #  if app.app_type == app.APP_TYPE_CHOICES.part5:
        if app.routeid is None:
            app.routeid = 1

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext['may_refer'] != "True":
            messages.error(self.request, 'Can not modify referrals on this application!')
            return HttpResponseRedirect(app.get_absolute_url())

#        else:
#            if app.state not in [app.APP_STATE_CHOICES.with_admin, app.APP_STATE_CHOICES.with_referee]:
#               # TODO: better/explicit error response.
#                messages.error(
#                    self.request, 'This application cannot be referred!')
#                return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationRefer, self).get(request, *args, **kwargs)

    def get_success_url(self):
        """Override to redirect to the referral's parent application detail view.
        """
        messages.success(self.request, 'Referral has been added! ')
        return reverse('application_refer', args=(self.object.application.pk,))

    def get_context_data(self, **kwargs):
        context = super(ApplicationRefer, self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['pk'])
        context['application_referrals'] = Referral.objects.filter(application=self.kwargs['pk'])
        app = Application.objects.get(pk=self.kwargs['pk'])
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        context = flow.getAccessRights(self.request, context, app.routeid, workflowtype)
        return context

    def get_initial(self):
        initial = super(ApplicationRefer, self).get_initial()
        # TODO: set the default period value based on application type.
        initial['period'] = 21
        return initial

    def get_form_kwargs(self):
        kwargs = super(ApplicationRefer, self).get_form_kwargs()
        kwargs['application'] = Application.objects.get(pk=self.kwargs['pk'])
        return kwargs

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationRefer, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        app = Application.objects.get(pk=self.kwargs['pk'])

#        if app.app_type == app.APP_TYPE_CHOICES.part5:
#            flow = Flow()
#            flow.get('part5')
#            nextroute = flow.getNextRoute('referral',app.routeid,"part5")
#            app.routeid = nextroute

        self.object = form.save(commit=False)
        self.object.application = app
        self.object.sent_date = date.today()
        self.object.save()
        # Set the application status to 'with referee'.
#        app.state = app.APP_STATE_CHOICES.with_referee
#        app.save()
        # TODO: the process of sending the application to the referee.
        # Generate a 'refer' action on the application:
        action = Action(
            content_object=app, category=Action.ACTION_CATEGORY_CHOICES.refer,
            user=self.request.user, action='Referred for conditions/feedback to {}'.format(self.object.referee))
        action.save()
        return super(ApplicationRefer, self).form_valid(form)

class ApplicationAssignNextAction(LoginRequiredMixin, UpdateView):
    """A view to allow an application to be assigned to an internal user or back to the customer.
    The ``action`` kwarg is used to define the new state of the application.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()

#        DefaultGroups = {}
#        DefaultGroups['admin'] = 'Processor'
#        DefaultGroups['assess'] = 'Assessor'
#        DefaultGroups['manager'] = 'Approver'
#        DefaultGroups['director'] = 'Director'
#        DefaultGroups['exec'] = 'Executive'
#        appt = "app_type1"
#        print hasattr(app, appt)
#        print getattr(app, appt)
#        print app.routeid

        if app.assignee is None:
            messages.error(self.request, 'Please Allocate an Assigned Person First')
            return HttpResponseRedirect(app.get_absolute_url())

        action = self.kwargs['action']

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)
        route = flow.getNextRouteObj(action, app.routeid, workflowtype)

        if action is "creator":
            if flowcontext['may_assign_to_creator'] != "True":
                messages.error(self.request, 'This application cannot be reassigned, Unknown Error')
                return HttpResponseRedirect(app.get_absolute_url())
        else:
            # nextroute = flow.getNextRoute(action,app.routeid,"part5")
            assign_action = flow.checkAssignedAction(action, flowcontext)
            if assign_action != True:
                if action in DefaultGroups['grouplink']:
                    messages.error(self.request, 'This application cannot be reassign to ' + DefaultGroups['grouplink'][action])
                    return HttpResponseRedirect(app.get_absolute_url())
                else:
                    messages.error(self.request, 'This application cannot be reassign, Unknown Error')
                    return HttpResponseRedirect(app.get_absolute_url())

        if action == 'referral':
            app_refs = Referral.objects.filter(application=app).count()
            Referral.objects.filter(application=app).update(status=Referral.REFERRAL_STATUS_CHOICES.referred)
            if app_refs == 0:
                messages.error(self.request, 'Unable to complete action as you have no referrals! ')
                return HttpResponseRedirect(app.get_absolute_url())
        if "required" in route:
            for fielditem in route["required"]:
                if hasattr(app, fielditem):
                    if getattr(app, fielditem) is None:
                        messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                        return HttpResponseRedirect(reverse('application_update', args=(app.pk,)))
                    appattr = getattr(app, fielditem)
                    if isinstance(appattr, unicode) or isinstance(appattr, str):
                        if len(appattr) == 0:
                            messages.error(self.request, 'Required Field ' + fielditem + ' is empty,  Please Complete')
                            return HttpResponseRedirect(reverse('application_update', args=(app.pk,)))

        return super(ApplicationAssignNextAction, self).get(request, *args, **kwargs)

    def get_initial(self):
        initial = super(ApplicationAssignNextAction, self).get_initial()
        initial['action'] = self.kwargs['action'] 
        initial['records'] = None
        return initial

# action = self.kwargs['action']
    def get_form_class(self):
        return apps_forms.ApplicationAssignNextAction

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationAssignNextAction, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_list')

    def form_valid(self, form):
        self.object = form.save(commit=False)
        forms_data = form.cleaned_data
        app = self.get_object()
        action = self.kwargs['action']

        # Upload New Files
        # doc = None
        # if self.request.FILES.get('records'):  # Uploaded new file.
        #    doc = Record()
        #    doc.upload = forms_data['records']
        #    doc.name = forms_data['records'].name
        #    doc.save()
        # print doc
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        DefaultGroups = flow.groupList()
        FriendlyGroupList = flow.FriendlyGroupList()
        flow.get(workflowtype)
        assessed_by = None

        if action == "creator":
            groupassignment = None
            assignee = app.submitted_by
        elif action == 'referral':
            groupassignment = None
            assignee = None
        else:
            assignee = None
            assessed_by = self.request.user 
            groupassignment = Group.objects.get(name=DefaultGroups['grouplink'][action])

        route = flow.getNextRouteObj(action, app.routeid, workflowtype)
        if route is None:
            messages.error(self.request, 'Error In Assigning Next Route, No routes Found')
            return HttpResponseRedirect(app.get_absolute_url())
        if route["route"] is None:
            messages.error(self.request, 'Error In Assigning Next Route, No routes Found')
            return HttpResponseRedirect(app.get_absolute_url())

        self.object.routeid = route["route"]
        self.object.state = route["state"]
        self.object.group = groupassignment
        self.object.assignee = assignee
        self.object.save()


        # this get uses the new route id to get title of new route and updates the route_status.
        workflowtype = flow.getWorkFlowTypeFromApp(self.object)
        flow.get(workflowtype)
        self.object.route_status = flow.json_obj[self.object.routeid]['title']
        self.object.save()

        comms = Communication()
        comms.application = app
        comms.comms_from = str(self.request.user.email)

        if action == 'creator': 
           comms.comms_to = "Form Creator"
        else:
           comms.comms_to = FriendlyGroupList['grouplink'][action] 
        comms.subject = route["title"]
        comms.details = forms_data['details']
        comms.state = route["state"]
        comms.comms_type = 4
        comms.save()

        if 'records_json' in self.request.POST:
            if is_json(self.request.POST['records_json']) is True:
                json_data = json.loads(self.request.POST['records_json'])
                for i in json_data:
                    doc = Record.objects.get(id=i['doc_id'])
                    comms.records.add(doc)
                    comms.save() 


#        if self.request.FILES.get('records'):
#            if Attachment_Extension_Check('multi', self.request.FILES.getlist('other_relevant_documents'), None) is False:
#                raise ValidationError('Other relevant documents contains and unallowed attachment extension.')
#
#            for f in self.request.FILES.getlist('records'):
#                doc = Record()
#                doc.upload = f
#                doc.name = f.name
#                doc.save()
#                comms.records.add(doc)
#        if doc:
#            comms.records.add(doc)

        if "stake_holder_communication" in route:
             self.send_stake_holder_comms(app) 

        emailcontext = {}
        emailcontext['app'] = self.object

        if action != "creator" and action != 'referral':
            emailcontext['groupname'] = DefaultGroups['grouplink'][action]
            emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
            emailGroup('Application Assignment to Group ' + DefaultGroups['grouplink'][action], emailcontext, 'application-assigned-to-group.html', None, None, None, DefaultGroups['grouplink'][action])
        elif action == "creator":
            emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
            emailcontext['person'] = assignee
            emailcontext['admin_comment'] = forms_data['sumbitter_comment']
            sendHtmlEmail([assignee.email], emailcontext['application_name'] + ' application requires more information ', emailcontext, 'application-assigned-to-submitter.html', None, None, None)
        elif action == "referral":
            emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
            emailApplicationReferrals(app.id, 'Application for Feedback ', emailcontext, 'application-assigned-to-referee.html', None, None, None)

        if self.object.state == '14':
        # Form Commpleted & Create Approval
            self.complete_application(app)
        if self.object.state == '10': 
            self.ammendment_approved(app) 
        if 'process' in route:
            if 'draft_completed' in route['process']:
                self.draft_completed(app)
            if 'final_completed' in route['process']:
                self.final_completed(app)

        # Record an action on the application:
        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.action, user=self.request.user,
            action='Next Step Application Assigned to group ({}) with action title ({}) and route id ({}) '.format(groupassignment, route['title'], self.object.routeid))
        action.save()

        return HttpResponseRedirect(self.get_success_url())

    def send_stake_holder_comms(self,app):
        # application-stakeholder-comms.html 
        # get applicant contact emails 
        if app.organisation:
           org_dels = Delegate.objects.filter(organisation=app.organisation) 
           for od in org_dels:
                # get all organisation contact emails and names
                StakeholderComms.objects.create(application=app,
                                                email=od.email_user.email,
                                                name=od.email_user.first_name + ' '+ od.email_user.last_name,
                                                sent_date=date.today(),
                                                role=1,
                                                comm_type=1
                )
                emailcontext = {'person': od.email_user.first_name + ' '+ od.email_user.last_name}    
                sendHtmlEmail([od.email_user.email], 'Appplication has progressed', emailcontext, 'application-stakeholder-comms.html', None, None, None)
             
        elif app.applicant:

               StakeholderComms.objects.create(application=app,
                                                email=app.applicant.email,
                                                name=app.applicant.first_name + ' '+ app.applicant.last_name,
                                                sent_date=date.today(),
                                                role=1,
                                                comm_type=1
               )
               emailcontext = {'person': app.applicant.first_name + ' '+ app.applicant.last_name}
               sendHtmlEmail([app.applicant.email], 'Appplication has progressed', emailcontext, 'application-stakeholder-comms.html', None, None, None)

               # get only applicant name and email
        
        # Get Sumitter information
        # submitter = app.submitted_by
        if app.applicant != app.submitted_by:
            StakeholderComms.objects.create(application=app,
                                       email=app.submitted_by.email,
                                       name=app.submitted_by.first_name + ' '+ app.submitted_by.last_name,
                                       sent_date=date.today(),
                                       role=2,
                                       comm_type=1
            )
            emailcontext = {'person': app.submitted_by.first_name + ' '+ app.submitted_by.last_name}
            sendHtmlEmail([app.submitted_by.email], 'Appplication has progressed', emailcontext, 'application-stakeholder-comms.html', None, None, None)


        public_feedback =  PublicationFeedback.objects.filter(application=app)
        for pf in public_feedback:
            StakeholderComms.objects.create(application=app,
                                       email=pf.email,
                                       name=pf.name,
                                       sent_date=date.today(),
                                       role=4,
                                       comm_type=1
            )
            emailcontext = {'person': pf.name}
            sendHtmlEmail([pf.email], 'Appplication has progressed', emailcontext, 'application-stakeholder-comms.html', None, None, None)


        # Get feedback
        # PublicationFeedback 
        refs = Referral.objects.filter(application=app)
        for ref in refs:
            StakeholderComms.objects.create(application=app,
                                       email=ref.referee.email,
                                       name=ref.referee.first_name + ' ' + ref.referee.last_name,
                                       sent_date=date.today(),
                                       role=3,
                                       comm_type=1
            )
            emailcontext = {'person': ref.referee.first_name + ' ' + ref.referee.last_name}
            sendHtmlEmail([ref.referee.email], 'Appplication has progressed', emailcontext, 'application-stakeholder-comms.html', None, None, None)


        # Get Referrals
        # Referral
        # app.pfpfpf        


    def draft_completed(self,app):
         emailcontext = {}
         emailcontext['app'] = app

#        if app.app_type == 3:
         emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
         emailcontext['person'] = app.submitted_by
         sendHtmlEmail([app.submitted_by.email], 'Draft Report - Part 5 - '+str(app.id), emailcontext, 'application-part5-draft-report.html', None, None, None)

    def final_completed(self,app):
         emailcontext = {}
         emailcontext['app'] = app

         if app.app_type == 3:
            emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
            emailcontext['person'] = app.submitted_by 
            sendHtmlEmail([app.submitted_by.email], 'Final Report - Part  - '+str(app.id), emailcontext, 'application-part5-final-report.html', None, None, None)

    def complete_application(self,app): 
        """Once and application is complete and approval needs to be created in the approval model.
        """
        approval = Approval.objects.create(
                                          app_type=app.app_type,
                                          title=app.title,
                                          applicant=app.applicant,
                                          organisation=app.organisation,
                                          application=app,
                                          start_date=app.assessment_start_date,
                                          expiry_date=app.expire_date,
                                          status=1
                                          )

        emailcontext = {}
        emailcontext['app'] = app
        emailcontext['approval'] = approval


        # applications/email/application-permit-proposal.html

        # email send after application completed..(issued)
        if app.app_type == 1:
           # Permit Proposal
           emailcontext['person'] = app.submitted_by 
           emailcontext['conditions_count'] = Condition.objects.filter(application=app).count()
           sendHtmlEmail([app.submitted_by.email], 'Permit - '+app.title, emailcontext, 'application-permit-proposal.html', None, None, None)

        elif app.app_type == 2:
           # Licence Proposal
           emailcontext['person'] = app.submitted_by
           sendHtmlEmail([app.submitted_by.email], 'Licence Permit - '+app.title, emailcontext, 'application-licence-permit-proposal.html', None, None, None)
        elif app.app_type == 3:
           # Licence Proposal
           emailcontext['person'] = app.submitted_by
           sendHtmlEmail([app.submitted_by.email], 'Determination - Part 5 - '+str(app.id)+' - '+str(app.location)+' - [Description of Works] - [Applicant]', emailcontext, 'application-determination.html', None, None, None)
        elif app.app_type == 10 or app.app_type == 11:
           # Permit & Licence Renewal 
           emailcontext['person'] = app.submitted_by
           sendHtmlEmail([app.submitted_by.email], 'Draft Report - Part 5 - '+str(app.id)+' - location - description of works - applicant', emailcontext, 'application-licence-permit-proposal.html', None, None, None)
         

        ####################
        # Disabling compliance creationg after approval ( this is now handle by cron script as we are not creating all future compliance all at once but only the next due complaince.
        return
        ################### 
        

        # For compliance ( create clearance of conditions )
        # get all conditions 
        conditions = Condition.objects.filter(application=app)

        # print conditions
        # create clearance conditions
        for c in conditions:
            
            start_date = app.proposed_commence
            end_date = c.due_date
            if c.recur_pattern == 1:
                  num_of_weeks = (end_date - start_date).days / 7.0
                  num_of_weeks_whole = str(num_of_weeks).split('.')
                  num_of_weeks_whole = num_of_weeks_whole[0]
                  week_freq = num_of_weeks / c.recur_freq
                  week_freq_whole = int(str(week_freq).split('.')[0])
                  loopcount = 1
                  loop_start_date = start_date
                  while loopcount <= week_freq_whole:
                      loopcount = loopcount + 1
                      week_date_plus = timedelta(weeks = c.recur_freq)

                      new_week_date = loop_start_date + week_date_plus
                      loop_start_date = new_week_date
                      compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=new_week_date,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                     )
                  
                  if week_freq > week_freq_whole:
                      compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=c.due_date,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                     )
            if c.recur_pattern == 2:
                 r = relativedelta(end_date, start_date)
                 num_of_months = float(r.years * 12 + r.months) / c.recur_freq
                 loopcount = 0
                 loop_start_date = start_date

                 while loopcount < int(num_of_months):
                      months_date_plus = loop_start_date + relativedelta(months=c.recur_freq)
                      loop_start_date = months_date_plus
                      loopcount = loopcount + 1
                      compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=months_date_plus,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                     )

                 if num_of_months > loopcount:
                      compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=end_date,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                   )

            if c.recur_pattern == 3: 
              
                 r = relativedelta(end_date, start_date)
                 if r.years > 0:
                     loopcount = 0
                     loop_start_date = start_date
                     while loopcount < int(r.years):
                           years_date_plus = loop_start_date + relativedelta(years=c.recur_freq)
                           loop_start_date = years_date_plus
                           loopcount = loopcount + 1
 
                           compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=years_date_plus,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                     )


                 if r.months > 0 or r.days > 0:
                     compliance = Compliance.objects.create(
                                      app_type=app.app_type,
                                      title=app.title,
                                      condition=c,
                                      approval_id=approval.id,
                                      applicant=approval.applicant,
                                      assignee=None,
                                      assessed_by=None,
                                      assessed_date=None,
                                      due_date=end_date,
                                      status=Compliance.COMPLIANCE_STATUS_CHOICES.future
                                   )

            #print c.iii


    def ammendment_approved(self,app):
        if app.approval_id: 
            approval = Approval.objects.get(id=app.approval_id)
            approval.ammendment_application = app
            approval.save()
        return

class ApplicationAssignPerson(LoginRequiredMixin, UpdateView):
    """A view to allow an application applicant to be assigned to a person 
    """
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()

        if app.state == 14:
           messages.error(self.request, 'This application is completed and cannot be assigned.')
           return HttpResponseRedirect("/")
             

        if app.group is None:
            messages.error(self.request, 'Unable to set Person Assignments as No Group Assignments Set!')
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationAssignPerson, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.AssignPersonForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationAssignPerson, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_update', args=(self.object.pk,))

    def form_valid(self, form):
        self.object = form.save(commit=True)
        app = self.object

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        DefaultGroups = flow.groupList()
        flow.get(workflowtype)
        emailcontext = {'person': app.assignee}
        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
        if self.request.user != app.assignee:
            sendHtmlEmail([app.assignee.email], emailcontext['application_name'] + ' application assigned to you ', emailcontext, 'application-assigned-to-person.html', None, None, None)
        

        # Record an action on the application:
        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
            action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_state_display()))
        action.save()
        if self.request.user != app.assignee:
            messages.success(self.request, 'Assign person completed')
            return HttpResponseRedirect(reverse('application_list'))
        else:
            messages.success(self.request, 'Assign person completed')
            return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ApplicationAssignPerson, self).get_initial()
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        initial['assigngroup'] = app.group
        return initial


class ComplianceAssignPerson(LoginRequiredMixin, UpdateView):
    """A view to allow an application applicant to be assigned to a person
    """
    model = Compliance 

    def get(self, request, *args, **kwargs):
        app = self.get_object()

#        if app.state == 14:
#           messages.error(self.request, 'This compliance is approved and cannot be assigned.')
#           return HttpResponseRedirect("/")

        return super(ComplianceAssignPerson, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.ComplianceAssignPersonForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ComplianceAssignPerson, self).post(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('compliance_approval_detail', args=(self.object.pk,))

    def form_valid(self, form):
        self.object = form.save(commit=True)
        app = self.object

        #flow = Flow()
        #workflowtype = flow.getWorkFlowTypeFromApp(app)
        #DefaultGroups = flow.groupList()
        #flow.get(workflowtype)
        #emailcontext = {'person': app.assignee}
        #emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
        #if self.request.user != app.assignee:
        #    sendHtmlEmail([app.assignee.email], emailcontext['application_name'] + ' application assigned to you ', emailcontext, 'application-assigned-to-person.html', None, None, None)


        # Record an action on the application:
        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
            action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_status_display()))
        action.save()
        if self.request.user != app.assignee:
            messages.success(self.request, 'Assign person completed')
            return HttpResponseRedirect(reverse('application_list'))
        else:
            messages.success(self.request, 'Assign person completed')
            return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ComplianceAssignPerson, self).get_initial()
        app = self.get_object()
        initial['assigngroup'] = app.group
        return initial
        #if app.routeid is None:
        #    app.routeid = 1

class ApplicationAssignApplicantCompany(LoginRequiredMixin, UpdateView):
    """A view to allow an application applicant to be assigned to a company holder
    """ 
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        #if app.group is None:
        #    messages.error(self.request, 'Unable to set Person Assignments as No Group Assignments Set!')
        #    return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationAssignApplicantCompany, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.AssignApplicantFormCompany

    def get_success_url(self, application_id):
        return reverse('application_update', args=(application_id,))

    def post(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationAssignApplicantCompany, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=True)
        self.object.applicant = None
        self.object.save()

        app = self.object

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        DefaultGroups = flow.groupList() 
        flow.get(workflowtype)
        emailcontext = {'person': app.assignee}
        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
        if self.object.assignee:
            action = Action(
                content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_state_display()))
            action.save()
        return HttpResponseRedirect(self.get_success_url(self.kwargs['pk']))

    def get_initial(self):
        initial = super(ApplicationAssignApplicantCompany, self).get_initial()
        app = self.get_object()
        initial['organisation'] = self.kwargs['organisation_id']
        return initial

class ApplicationAssignApplicant(LoginRequiredMixin, UpdateView):
    """A view to allow an application applicant details to be reassigned to a different applicant name and 
       is only can only be set by and admin officer.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        #if app.group is None:
        #    messages.error(self.request, 'Unable to set Person Assignments as No Group Assignments Set!')
        #    return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationAssignApplicant, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.AssignApplicantForm


    def get_success_url(self, application_id):
        return reverse('application_update', args=(application_id,))

    def post(self, request, *args, **kwargs):

        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")


        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationAssignApplicant, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.organisation = None
        self.object.save()

        app = self.object

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        DefaultGroups = flow.groupList()
        flow.get(workflowtype)
        emailcontext = {'person': app.assignee}
        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
#        if self.request.user != app.assignee:
#            sendHtmlEmail([app.assignee.email], emailcontext['application_name'] + ' application assigned to you ', emailcontext, 'application-assigned-to-person.html', None, None, None)

        # Record an action on the application:
        if self.object.assignee:
            action = Action(
                content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_state_display()))
            action.save()
        return HttpResponseRedirect(self.get_success_url(self.kwargs['pk']))

    def get_initial(self):
        initial = super(ApplicationAssignApplicant, self).get_initial()
        app = self.get_object()
        initial['applicant'] = self.kwargs['applicantid']
        return initial

class ApplicationAssign(LoginRequiredMixin, UpdateView):
    """A view to allow an application to be assigned to an internal user or back to the customer.
    The ``action`` kwarg is used to define the new state of the application.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        if self.kwargs['action'] == 'customer':
            # Rule: application can go back to customer when only status is
            # 'with admin'.
            if app.state != app.APP_STATE_CHOICES.with_admin:
                messages.error(
                    self.request, 'This application cannot be returned to the customer!')
                return HttpResponseRedirect(app.get_absolute_url())
        if self.kwargs['action'] == 'assess':
            # Rule: application can be assessed when status is 'with admin',
            # 'with referee' or 'with manager'.
            if app.app_type == app.APP_TYPE_CHOICES.part5:
                flow = Flow()
                flow.get('part5')
                flowcontext = {}
                flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, 'part5')
                if flowcontext["may_assign_assessor"] != "True":
                    messages.error(self.request, 'This application cannot be assigned to an assessor!')
                    return HttpResponseRedirect(app.get_absolute_url())
            else:
                if app.state not in [app.APP_STATE_CHOICES.with_admin, app.APP_STATE_CHOICES.with_referee, app.APP_STATE_CHOICES.with_manager]:
                    messages.error(self.request, 'This application cannot be assigned to an assessor!')
                    return HttpResponseRedirect(app.get_absolute_url())
        # Rule: only the assignee (or a superuser) can assign for approval.
        if self.kwargs['action'] == 'approve':
            if app.app_type == app.APP_TYPE_CHOICES.part5:
                flow = Flow()
                flow.get('part5')
                flowcontext = {}
                flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, 'part5')

                if flowcontext["may_submit_approval"] != "True":
                    messages.error(self.request, 'This application cannot be assigned to an assessor!')
                    return HttpResponseRedirect(app.get_absolute_url())
            else:
                if app.state != app.APP_STATE_CHOICES.with_assessor:
                    messages.error(self.request, 'You are unable to assign this application for approval/issue!')
                    return HttpResponseRedirect(app.get_absolute_url())
                if app.assignee != request.user and not request.user.is_superuser:
                    messages.error(self.request, 'You are unable to assign this application for approval/issue!')
                    return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationAssign, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        if self.kwargs['action'] == 'customer':
            return apps_forms.AssignCustomerForm
        elif self.kwargs['action'] == 'process':
            return apps_forms.AssignProcessorForm
        elif self.kwargs['action'] == 'assess':
            return apps_forms.AssignAssessorForm
        elif self.kwargs['action'] == 'approve':
            return apps_forms.AssignApproverForm
        elif self.kwargs['action'] == 'assign_emergency':
            return apps_forms.AssignEmergencyForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationAssign, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        app = self.object
        if self.kwargs['action'] == 'customer':
            messages.success(self.request, 'Application {} has been assigned back to customer'.format(self.object.pk))
        else:
            messages.success(self.request, 'Application {} has been assigned to {}'.format(self.object.pk, self.object.assignee.get_full_name()))
        if self.kwargs['action'] == 'customer':
            # Assign the application back to the applicant and make it 'draft'
            # status.
            self.object.assignee = self.object.applicant
            self.object.state = self.object.APP_STATE_CHOICES.draft
            # TODO: email the feedback back to the customer.
        if self.kwargs['action'] == 'assess':
            if app.app_type == app.APP_TYPE_CHOICES.part5:
                flow = Flow()
                flow.get('part5')
                nextroute = flow.getNextRoute('assess', app.routeid, "part5")
                self.object.routeid = nextroute
            self.object.state = self.object.APP_STATE_CHOICES.with_assessor
        if self.kwargs['action'] == 'approve':
            if app.app_type == app.APP_TYPE_CHOICES.part5:
                flow = Flow()
                flow.get('part5')
                nextroute = flow.getNextRoute('manager', app.routeid, "part5")
                self.object.routeid = nextroute
            self.object.state = self.object.APP_STATE_CHOICES.with_manager
        if self.kwargs['action'] == 'process':
            if app.app_type == app.APP_TYPE_CHOICES.part5:
                flow = Flow()
                flow.get('part5')
                nextroute = flow.getNextRoute('admin', app.routeid, "part5")
                self.object.routeid = nextroute

            self.object.state = self.object.APP_STATE_CHOICES.with_manager
        self.object.save()
        if self.kwargs['action'] == 'customer':
            # Record the feedback on the application:
            d = form.cleaned_data
            action = Action(
                content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.communicate, user=self.request.user,
                action='Feedback provided to applicant: {}'.format(d['feedback']))
            action.save()
        # Record an action on the application:
        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
            action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_state_display()))
        action.save()
        return HttpResponseRedirect(self.get_success_url())

# have disbled the url..  this should be covered in the workflow.
class ApplicationDiscard(LoginRequiredMixin, UpdateView):
    """Allows and applicant to discard the application.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        app = self.get_object()

        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if app.state == 1:
           if request.user.id == app.assignee.id:
               donothing = ""
           elif admin_staff is True:
               donothing = ""
           else:
               messages.error(self.request, 'Sorry you are not authorised')
               return HttpResponseRedirect(self.get_success_url())
        else:
           messages.error(self.request, 'Sorry you are not authorised')
           return HttpResponseRedirect(self.get_success_url())        
        #if app.group is None:
        #    messages.error(self.request, 'Unable to set Person Assignments as No Group Assignments Set!')
        #    return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationDiscard, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.ApplicationDiscardForm

    def get_success_url(self):
        return reverse('home_page')

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ApplicationDiscard, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.state = 17
        self.object.route_status = "Deleted"
        self.object.save()

        # Record an action on the application:
        action = Action(
           content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
               action='Application Discard')
        action.save()
        messages.success(self.request, "Your application has been discard")
        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ApplicationDiscard, self).get_initial()
        app = self.get_object()
        return initial

class ComplianceActions(DetailView):
    model = Compliance 
    template_name = 'applications/compliance_actions.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceActions, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ComplianceActions, self).get_context_data(**kwargs)
        app = self.get_object()
        # TODO: define a GenericRelation field on the Application model.
        context['actions'] = Action.objects.filter(
            content_type=ContentType.objects.get_for_model(app), object_id=app.pk).order_by('-timestamp')
        return context

class ComplianceSubmit(LoginRequiredMixin, UpdateView):
    """Allows and applicant to discard the application.
    """
    model = Compliance

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = Delegate.objects.filter(email_user=self.request.user, organisation=self.object.organisation).count()

        if admin_staff == True:
           pass
        elif self.request.user.groups.filter(name__in=['Assessor']).exists():
           pass
        elif self.request.user == self.object.applicant:
           pass
        elif org == 1:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceSubmit, self).get(request, *args, **kwargs)

    def get_form_class(self):
        return apps_forms.ComplianceSubmitForm

    def get_success_url(self):
        return reverse('compliance_condition_complete', args=(self.object.id,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ComplianceSubmit, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.status = 9
        self.object.submit_date = datetime.now()
        self.object.submitted_by = self.request.user 
        assigngroup = Group.objects.get(name='Assessor')
        self.object.group = assigngroup
        self.object.save() 
        # Record an action on the application:
        action = Action(
           content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
               action='Compliance Submitted')
        action.save()
        messages.success(self.request, "Your compliance has beeen submitted for approval")

        emailcontext = {}
        #emailcontext['groupname'] = DefaultGroups['grouplink'][action]
        emailcontext['clearance_id'] = self.object.id
        emailGroup('New Clearance of Condition Submitted', emailcontext, 'clearance-of-condition-submitted.html', None, None, None, 'Assessor')

        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ComplianceSubmit, self).get_initial()
        app = self.get_object()
        return initial


class ComplianceStaff(LoginRequiredMixin, UpdateView):
    """Allows and applicant to discard the application.
    """
    model = Compliance

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        elif self.request.user.groups.filter(name__in=['Assessor']).exists():
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        return super(ComplianceStaff, self).get(request, *args, **kwargs)

    def get_form_class(self):
        return apps_forms.ComplianceStaffForm

    def get_success_url(self):
        return reverse('home_page')

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ComplianceStaff, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)

        action = self.kwargs['action']
        if action == 'approve':
             self.object.status = 4
             self.object.assessed_by = self.request.user
             self.object.assessed_date = date.today()
             self.object.assignee = None
             messages.success(self.request, "Compliance has been approved.")
             action = Action(
                  content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                  action='Compliance has been approved')
             action.save()

             emailcontext = {}
             emailcontext['app'] = self.object
             emailcontext['person'] = self.object.submitted_by
             emailcontext['body'] = "Your clearance of condition has been approved"
             sendHtmlEmail([self.object.submitted_by.email], 'Clearance of condition has been approved', emailcontext, 'clearance-approved.html', None, None, None)

        elif action == 'manager':
             self.object.status = 6
             #self.object.group
             approver = Group.objects.get(name='Approver')
             self.object.assignee = None
             self.object.group = approver
             messages.success(self.request, "Compliance has been assigned to the manager group.")
             action = Action(
                  content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                  action='Compliance assigned to Manager')
             action.save()
 
             emailcontext = {}
             emailcontext['clearance_id'] = self.object.id
             emailGroup('Clearance of Condition Assigned to Manager Group', emailcontext, 'clearance-of-condition-assigned-groups.html', None, None, None, 'Approver')

        elif action == 'holder':
             self.object.status = 7
             self.object.group = None
             self.object.assignee = None
             messages.success(self.request, "Compliance has been assigned to the holder.") 
             action = Action(
                  content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                  action='Compliance has been return to holder')
             action.save()

             emailcontext = {}
             emailcontext['app'] = self.object
             emailcontext['person'] = self.object.submitted_by
             emailcontext['body'] = "Your clearance of condition requires additional information."
             sendHtmlEmail([self.object.submitted_by.email], 'Your clearance of condition requires additional information please login and resubmit with additional information.', emailcontext, 'clearance-holder.html', None, None, None)

        elif action == 'assessor':
             self.object.status = 5
             self.object.group = None
             self.object.assignee = None
             assigngroup = Group.objects.get(name='Assessor')
             self.object.group = assigngroup
             messages.success(self.request, "Compliance has been assigned to the assessor.")
             action = Action(
                  content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
                  action='Compliance has been return to holder')
             action.save()

             emailcontext = {}
             emailcontext['clearance_id'] = self.object.id
             emailGroup('Clearance of Condition Assigned to Assessor Group', emailcontext, 'clearance-of-condition-assigned-groups.html', None, None, None, 'Assessor')

    
        self.object.save()
        # Record an action on the application:
        return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ComplianceStaff, self).get_initial()
        app = self.get_object()
        initial['action'] = self.kwargs['action']
        return initial

class ApplicationIssue(LoginRequiredMixin, UpdateView):
    """A view to allow a manager to issue an assessed application.
    """
    model = Application

    def get(self, request, *args, **kwargs):
        # Rule: only the assignee (or a superuser) can perform this action.
        app = self.get_object()
        if app.assignee == request.user or request.user.is_superuser:
            return super(ApplicationIssue, self).get(request, *args, **kwargs)
        messages.error(
            self.request, 'You are unable to issue this application!')
        return HttpResponseRedirect(app.get_absolute_url())

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url()+'update/')
        return super(ApplicationIssue, self).post(request, *args, **kwargs)

    def get_form_class(self):
        app = self.get_object()

        if app.app_type == app.APP_TYPE_CHOICES.emergency:
            return apps_forms.ApplicationEmergencyIssueForm
        else:
            return apps_forms.ApplicationIssueForm

    def get_initial(self):
        initial = super(ApplicationIssue, self).get_initial()
        app = self.get_object()

        if app.app_type == app.APP_TYPE_CHOICES.emergency:
            if app.organisation:
                initial['holder'] = app.organisation.name
                initial['abn'] = app.organisation.abn
            elif app.applicant:
                initial['holder'] = app.applicant.get_full_name()

        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)
        d = form.cleaned_data
        if self.request.POST.get('issue') == 'Issue':
            self.object.state = self.object.APP_STATE_CHOICES.current
            self.object.assignee = None
            # Record an action on the application:
            action = Action(
                content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.issue,
                user=self.request.user, action='Application issued')
            action.save()
            if self.object.app_type == self.object.APP_TYPE_CHOICES.emergency:
                self.object.issue_date = date.today()

                msg = """<strong>The emergency works has been successfully issued.</strong><br />
                <br />
                <strong>Emergency Works:</strong> \tEW-{0}<br />
                <strong>Date / Time:</strong> \t{1}<br />
                <br />
                <a href="{2}">{3}</a>
                <br />
                """
                if self.object.applicant:
                    msg = msg + """The Emergency Works has been emailed."""
                else:
                    msg = msg + """The Emergency Works needs to be printed and posted."""
                messages.success(self.request, msg.format(self.object.pk, self.object.issue_date.strftime('%d/%m/%Y'),
                                                          self.get_success_url() + "pdf", 'EmergencyWorks.pdf'))
            else:
                messages.success(
                    self.request, 'Application {} has been issued'.format(self.object.pk))
        elif self.request.POST.get('decline') == 'Decline':
            self.object.state = self.object.APP_STATE_CHOICES.declined
            self.object.assignee = None
            # Record an action on the application:
            action = Action(
                content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.decline,
                user=self.request.user, action='Application declined')
            action.save()
            messages.warning(
                self.request, 'Application {} has been declined'.format(self.object.pk))
        self.object.save()

        # TODO: logic around emailing/posting the application to the customer.
        return HttpResponseRedirect(self.get_success_url())

class OLDComplianceAssignPerson(LoginRequiredMixin, UpdateView):
    """A view to allow an application applicant to be assigned to a person
    """
    model = Compliance 

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        if app.group is None:
            messages.error(self.request, 'Unable to set Person Assignments as No Group Assignments Set!')
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ApplicationAssignPerson, self).get(request, *args, **kwargs)

    def get_form_class(self):
        # Return the specified form class
        return apps_forms.AssignPersonForm

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().get_absolute_url())
        return super(ComplianceAssignPerson, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=True)
        app = self.object

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        DefaultGroups = flow.groupList()
        flow.get(workflowtype)
        emailcontext = {'person': app.assignee}
        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[app.app_type]
        if self.request.user != app.assignee:
            sendHtmlEmail([app.assignee.email], emailcontext['application_name'] + ' application assigned to you ', emailcontext, 'application-assigned-to-person.html', None, None, None)

        # Record an action on the application:
#        action = Action(
#            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.assign, user=self.request.user,
#            action='Assigned application to {} (status: {})'.format(self.object.assignee.get_full_name(), self.object.get_state_display()))
#        action.save()
        if self.request.user != app.assignee:
            return HttpResponseRedirect(reverse('application_list'))
        else:
            return HttpResponseRedirect(self.get_success_url())

    def get_initial(self):
        initial = super(ComplianceAssignPerson, self).get_initial()
        app = self.get_object()
        if app.routeid is None:
            app.routeid = 1
        initial['assigngroup'] = app.group
        return initial

class ReferralComplete(LoginRequiredMixin, UpdateView):
    """A view to allow a referral to be marked as 'completed'.
    """
    model = Referral
    form_class = apps_forms.ReferralCompleteForm

    def get(self, request, *args, **kwargs):
        app = self.get_object()
        refcount = Referral.objects.filter(application=app,referee=self.request.user).count()
        if refcount == 1:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        # Rule: can't mark a referral completed more than once.
#        if referral.response_date:
        if referral.status != Referral.REFERRAL_STATUS_CHOICES.referred:
            messages.error(self.request, 'This referral is already completed!')
            return HttpResponseRedirect(referral.application.get_absolute_url())
        # Rule: only the referee (or a superuser) can mark a referral
        # "complete".
        if referral.referee == request.user or request.user.is_superuser:
            return super(ReferralComplete, self).get(request, *args, **kwargs)
        messages.error(
            self.request, 'You are unable to mark this referral as complete!')
        return HttpResponseRedirect(referral.application.get_absolute_url())

    def get_context_data(self, **kwargs):
        context = super(ReferralComplete, self).get_context_data(**kwargs)
        self.template_name = 'applications/referral_complete_form.html'
        context['application'] = self.get_object().application
        return context

    def post(self, request, *args, **kwargs):
        app = self.get_object()
        refcount = Referral.objects.filter(application=app,referee=self.request.user).count()
        if refcount == 1:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ReferralComplete, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.response_date = date.today()
        self.object.status = Referral.REFERRAL_STATUS_CHOICES.responded
        self.object.save()
        app = self.object.application
        # Record an action on the referral's application:
        action = Action(
            content_object=app, user=self.request.user,
            action='Referral to {} marked as completed'.format(self.object.referee))
        action.save()
        # If there are no further outstanding referrals, then set the
        # application status to "with admin".
#        if not Referral.objects.filter(
#                application=app, status=Referral.REFERRAL_STATUS_CHOICES.referred).exists():
#            app.state = Application.APP_STATE_CHOICES.with_admin
#            app.save()
        refnextaction = Referrals_Next_Action_Check()
        refactionresp = refnextaction.get(app)
        if refactionresp == True:
            refnextaction.go_next_action(app)
            # Record an action.
            action = Action(
                content_object=app,
                action='No outstanding referrals, application status set to "{}"'.format(app.get_state_display()))
            action.save()

        return HttpResponseRedirect(app.get_absolute_url())


class ReferralRecall(LoginRequiredMixin, UpdateView):
    model = Referral
    form_class = apps_forms.ReferralRecallForm
    template_name = 'applications/referral_recall.html'

    def get(self, request, *args, **kwargs):
        referral = self.get_object()

        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        # Rule: can't recall a referral that is any other status than
        # 'referred'.
        if referral.status != Referral.REFERRAL_STATUS_CHOICES.referred:
            messages.error(self.request, 'This referral is already completed!')
            return HttpResponseRedirect(referral.application.get_absolute_url())
        return super(ReferralRecall, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralRecall, self).get_context_data(**kwargs)
        context['referral'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ReferralRecall, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        ref = self.get_object()
        ref.status = Referral.REFERRAL_STATUS_CHOICES.recalled
        ref.save()
        # Record an action on the referral's application:
        action = Action(
            content_object=ref.application, user=self.request.user,
            action='Referral to {} recalled'.format(ref.referee))
        action.save()

        #  check to see if there is any uncompleted/unrecalled referrals
        #  If no more pending referrals than more to next step in workflow
        refnextaction = Referrals_Next_Action_Check()
        refactionresp = refnextaction.get(ref.application)

        if refactionresp == True:
            refnextaction.go_next_action(ref.application)
            action = Action(
                content_object=ref.application, user=self.request.user,
                action='All Referrals Completed, Progress to next Workflow Action {} '.format(ref.referee))
            action.save()

        return HttpResponseRedirect(ref.application.get_absolute_url())


class ReferralResend(LoginRequiredMixin, UpdateView):
    model = Referral
    form_class = apps_forms.ReferralResendForm
    template_name = 'applications/referral_resend.html'

    def get(self, request, *args, **kwargs):
        referral = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        # Rule: can't recall a referral that is any other status than
        # 'referred'.
        if referral.status != Referral.REFERRAL_STATUS_CHOICES.recalled & referral.status != Referral.REFERRAL_STATUS_CHOICES.responded:
            messages.error(self.request, 'This referral is already completed!' + str(referral.status) + str(Referral.REFERRAL_STATUS_CHOICES.responded))
            return HttpResponseRedirect(referral.application.get_absolute_url())
        return super(ReferralResend, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralResend, self).get_context_data(**kwargs)
        context['referral'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ReferralResend, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        ref = self.get_object()
        ref.status = Referral.REFERRAL_STATUS_CHOICES.referred
        ref.save()
        # Record an action on the referral's application:
        action = Action(
            content_object=ref.application, user=self.request.user,
            action='Referral to {} resend '.format(ref.referee))
        action.save()

        return HttpResponseRedirect(ref.application.get_absolute_url())


class ReferralRemind(LoginRequiredMixin, UpdateView):
    model = Referral
    form_class = apps_forms.ReferralRemindForm
    template_name = 'applications/referral_remind.html'

    def get(self, request, *args, **kwargs):
        referral = self.get_object()

        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")


        if referral.status != Referral.REFERRAL_STATUS_CHOICES.referred:
            messages.error(self.request, 'This referral is already completed!')
            return HttpResponseRedirect(referral.application.get_absolute_url())
        return super(ReferralRemind, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralRemind, self).get_context_data(**kwargs)
        context['referral'] = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ReferralRemind, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        ref = self.get_object()
        emailcontext = {}
        emailcontext['person'] = ref.referee
        emailcontext['application_id'] = ref.application.id
        emailcontext['application_name'] = Application.APP_TYPE_CHOICES[ref.application.app_type]

        sendHtmlEmail([ref.referee.email], 'Application for Feedback Reminder', emailcontext, 'application-assigned-to-referee.html', None, None, None)

        action = Action(
            content_object=ref.application, user=self.request.user,
            action='Referral to {} reminded'.format(ref.referee))
        action.save()
        return HttpResponseRedirect(ref.application.get_absolute_url())


class ReferralDelete(LoginRequiredMixin, UpdateView):
    model = Referral
    form_class = apps_forms.ReferralDeleteForm
    template_name = 'applications/referral_delete.html'

    def get(self, request, *args, **kwargs):
        referral = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if referral.status != Referral.REFERRAL_STATUS_CHOICES.with_admin:
            messages.error(self.request, 'This referral is already completed!')
            return HttpResponseRedirect(referral.application.get_absolute_url())
        return super(ReferralDelete, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ReferralDelete, self).get_context_data(**kwargs)
        context['referral'] = self.get_object()
        return context

    def get_success_url(self, application_id):
        return reverse('application_refer', args=(application_id,))

    def post(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        if admin_staff == True:
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")

        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ReferralDelete, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        ref = self.get_object()
        application_id = ref.application.id
        ref.delete()
        # Record an action on the referral's application:
        action = Action(
            content_object=ref.application, user=self.request.user,
            action='Referral to {} delete'.format(ref.referee))
        action.save()
        return HttpResponseRedirect(self.get_success_url(application_id))


#class ComplianceList(ListView):
#    model = Compliance
#
#    def get_queryset(self):
#        qs = super(ComplianceList, self).get_queryset()
#        # Did we pass in a search string? If so, filter the queryset and return
#        # it.
#        if 'q' in self.request.GET and self.request.GET['q']:
#            query_str = self.request.GET['q']
#            # Replace single-quotes with double-quotes
#            query_str = query_str.replace("'", r'"')
#            # Filter by applicant__email, assignee__email, compliance
#            query = get_query(
#                query_str, ['applicant__email', 'assignee__email', 'compliance'])
#            qs = qs.filter(query).distinct()
#        return qs

class ComplianceApprovalDetails(LoginRequiredMixin,DetailView):
    # model = Approval
    model = Compliance
    template_name = 'applications/compliance_detail.html' 

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = Delegate.objects.filter(email_user=self.request.user, organisation=self.object.organisation).count()
       
        if admin_staff == True:
           pass
        elif self.request.user.groups.filter(name__in=['Assessor']).exists():
           pass
        elif self.request.user == self.object.applicant:
           pass
        elif org == 1: 
           pass
        else:
           messages.error(self.request, 'Forbidden from viewing this page.')
           return HttpResponseRedirect("/")
        return super(ComplianceApprovalDetails, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ComplianceApprovalDetails, self).get_context_data(**kwargs)
        app = self.get_object()
        # context['conditions'] = Compliance.objects.filter(approval_id=app.id)
        context['conditions'] = Compliance.objects.filter(id=app.id)
        return context

class ComplianceSubmitComplete(LoginRequiredMixin,DetailView):
#   model = Approval
    model = Compliance
    template_name = 'applications/compliance_complete.html'

    def get_context_data(self, **kwargs):
        context = super(ComplianceSubmitComplete, self).get_context_data(**kwargs)
        app = self.get_object()
        # context['conditions'] = Compliance.objects.filter(approval_id=app.id)
        context['conditions'] = Compliance.objects.filter(id=app.id)
        return context

class ComplianceComplete(LoginRequiredMixin,UpdateView):
    model = Compliance
    template_name = 'applications/compliance_update.html'
    form_class = apps_forms.ComplianceComplete

    def get_context_data(self, **kwargs):
        context = super(ComplianceComplete, self).get_context_data(**kwargs)
        app = self.get_object()
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
           compliance = Compliance.objects.get(id=kwargs['pk'])
           return HttpResponseRedirect(reverse("compliance_approval_detail", args=(compliance.approval_id,)))
        return super(ComplianceComplete, self).post(request, *args, **kwargs)

    def get_initial(self):
        initial = super(ComplianceComplete, self).get_initial()
        multifilelist = []

        records = self.object.records.all()
        for b1 in records:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            multifilelist.append(fileitem)
        initial['records'] = multifilelist
        return initial

    def form_valid(self, form):
        self.object = form.save(commit=False)

        for filelist in self.object.records.all():
             if 'records-clear_multifileid-' + str(filelist.id) in form.data:
                   self.object.records.remove(filelist)

        if self.request.FILES.get('records'):

            if Attachment_Extension_Check('multi', self.request.FILES.getlist('records'), None) is False:
                raise ValidationError('Documents contains and unallowed attachment extension.')

            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.name = f.name
                # print f.name
                doc.save()
                self.object.records.add(doc)
                # print self.object.records

        form.save()
        form.save_m2m()
        return HttpResponseRedirect(reverse("compliance_approval_detail", args=(self.object.id,)))

# this is theory shoudl be able to be deleted.  need to chekc first.
class ComplianceCreate(LoginRequiredMixin, ModelFormSetView):
    model = Compliance
    form_class = apps_forms.ComplianceCreateForm
    template_name = 'applications/compliance_formset.html'
    fields = ['condition', 'compliance']

    def get_application(self):
        return Application.objects.get(pk=self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        context = super(ComplianceCreate, self).get_context_data(**kwargs)
        app = self.get_application()
        context['application'] = app
        return context

    def get_initial(self):
        # Return a list of dicts, each containing a reference to one condition.
        app = self.get_application()
        conditions = app.condition_set.all()
        return [{'condition': c} for c in conditions]

    def get_factory_kwargs(self):
        kwargs = super(ComplianceCreate, self).get_factory_kwargs()
        app = self.get_application()
        conditions = app.condition_set.all()
        # Set the number of forms in the set to equal the number of conditions.
        kwargs['extra'] = len(conditions)
        return kwargs

    def get_extra_form_kwargs(self):
        kwargs = super(ComplianceCreate, self).get_extra_form_kwargs()
        kwargs['application'] = self.get_application()
        return kwargs

    def formset_valid(self, formset):
        for form in formset:
            data = form.cleaned_data
            # If text has been input to the compliance field, create a new
            # compliance object.
            if 'compliance' in data and data.get('compliance', None):
                new_comp = form.save(commit=False)
                new_comp.applicant = self.request.user
                new_comp.application = self.get_application()
                new_comp.submit_date = date.today()
                # TODO: handle the uploaded file.
                new_comp.save()
                # Record an action on the compliance request's application:
                action = Action(
                    content_object=new_comp.application, user=self.request.user,
                    action='Request for compliance created')
                action.save()
        messages.success(
            self.request, 'New requests for compliance have been submitted.')
        return super(ComplianceCreate, self).formset_valid(formset)

    def get_success_url(self):
        return reverse('application_detail', args=(self.get_application().pk,))


class WebPublish(LoginRequiredMixin, UpdateView):
    model = Application
    form_class = apps_forms.ApplicationWebPublishForm

    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])
        return super(WebPublish, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_update', args=(self.kwargs['pk'],))

    def get_context_data(self, **kwargs):
        context = super(WebPublish,
                        self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['pk'])
        return context

    def get_initial(self):
        initial = super(WebPublish, self).get_initial()
        initial['application'] = self.kwargs['pk']

        current_date = datetime.now().strftime('%d/%m/%Y')

        publish_type = self.kwargs['publish_type']
        if publish_type in 'documents':
            initial['publish_documents'] = current_date
        elif publish_type in 'draft':
            initial['publish_draft_report'] = current_date
        elif publish_type in 'final':
            initial['publish_final_report'] = current_date
        elif publish_type in 'determination':
            initial['publish_determination_report'] = current_date

        initial['publish_type'] = self.kwargs['publish_type']
        # try:
        #    pub_news = PublicationNewspaper.objects.get(
        #    application=self.kwargs['pk'])
        # except:
        #    pub_news = None
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(WebPublish, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        forms_data = form.cleaned_data
        self.object = form.save(commit=True)
        publish_type = self.kwargs['publish_type']

        current_date = datetime.now().strftime('%Y-%m-%d')

        if publish_type in 'documents':
            self.object.publish_documents = current_date
            action = Action(
               content_object=self.object, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.publish,
               action='Publish Documents')
            action.save()

        elif publish_type in 'draft':
            action = Action(
               content_object=self.object, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.publish,
               action='Publish Draft')
            action.save()  

            self.object.publish_draft_report = current_date
        elif publish_type in 'final': 
            action = Action(
               content_object=self.object, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.publish,
               action='Publish Final')
            action.save()
            self.object.publish_final_report = current_date
        elif publish_type in 'determination':
            action = Action(
               content_object=self.object, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.publish,
               action='Publish Determination')
            action.save()
            self.object.publish_determination_report = current_date

        return super(WebPublish, self).form_valid(form)


class NewsPaperPublicationCreate(LoginRequiredMixin, CreateView):
    model = PublicationNewspaper
    form_class = apps_forms.NewsPaperPublicationCreateForm

    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)


#       if flowcontext.state != app.APP_STATE_CHOICES.draft:
        if flowcontext["may_update_publication_newspaper"] != "True":
                    messages.error(
                          self.request, "Can't add new newspaper publication to this application")
                    return HttpResponseRedirect(app.get_absolute_url())
        return super(NewsPaperPublicationCreate, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.kwargs['pk'],))

    def get_context_data(self, **kwargs):
        context = super(NewsPaperPublicationCreate,
                       self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['pk'])
        return context

    def get_initial(self):
        initial = super(NewsPaperPublicationCreate, self).get_initial()
        initial['application'] = self.kwargs['pk']

           # try:
                #    pub_news = PublicationNewspaper.objects.get(
                #    application=self.kwargs['pk'])
                # except:
                #    pub_news = None
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())    
    
        return super(NewsPaperPublicationCreate, self).post(request, *args, **kwargs)
    def form_valid(self, form):
        forms_data = form.cleaned_data
        self.object = form.save(commit=True)
        if self.request.FILES.get('records'):
            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)

        action = Action(
            content_object=self.object.application, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.create,
            action='Newspaper Publication ({} {}) '.format(self.object.newspaper, self.object.date) )
        action.save()

        return super(NewsPaperPublicationCreate, self).form_valid(form)


class NewsPaperPublicationUpdate(LoginRequiredMixin, UpdateView):
    model = PublicationNewspaper
    form_class = apps_forms.NewsPaperPublicationCreateForm

    def get(self, request, *args, **kwargs):
        #app = self.get_object().application_set.first()
        PubNew = PublicationNewspaper.objects.get(pk=self.kwargs['pk'])
        app = Application.objects.get(pk=PubNew.application.id)
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        if flowcontext["may_update_publication_newspaper"] != "True":
            messages.error(self.request, "Can't update newspaper publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())
        # Rule: can only change a vessel if the parent application is status
        # 'draft'.
            # if app.state != Application.APP_STATE_CHOICES.draft:
            #    messages.error(
            #        self.request, 'You can only change a publication details when the application is "draft" status')
#        return HttpResponseRedirect(app.get_absolute_url())
        return super(NewsPaperPublicationUpdate, self).get(request, *args, **kwargs)

    def get_initial(self):
        initial = super(NewsPaperPublicationUpdate, self).get_initial()
#       initial['application'] = self.kwargs['pk']

        try:
            pub_news = PublicationNewspaper.objects.get(pk=self.kwargs['pk'])
        except:
            pub_news = None

        multifilelist = []
        if pub_news:
            records = pub_news.records.all()
            for b1 in records:
                fileitem = {}
                fileitem['fileid'] = b1.id
                fileitem['path'] = b1.upload.name
                multifilelist.append(fileitem)
        initial['records'] = multifilelist
        return initial

    def get_context_data(self, **kwargs):
        context = super(NewsPaperPublicationUpdate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Update Newspaper Publication details'
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
 #           print self.get_object().application.pk
#            app = self.get_object().application_set.first()
            return HttpResponseRedirect(reverse('application_detail', args=(self.get_object().application.pk,)))
        return super(NewsPaperPublicationUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        app = Application.objects.get(pk=self.object.application.id)

        pub_news = PublicationNewspaper.objects.get(pk=self.kwargs['pk'])

        records = pub_news.records.all()
        for filelist in records:
            if 'records-clear_multifileid-' + str(filelist.id) in form.data:
                 pub_news.records.remove(filelist)

        if self.request.FILES.get('records'):
            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)

        action = Action(
            content_object=self.object.application, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
            action='Newspaper Publication ({} {}) '.format(self.object.newspaper, self.object.date) )
        action.save()


        return HttpResponseRedirect(app.get_absolute_url())


class NewsPaperPublicationDelete(LoginRequiredMixin, DeleteView):
    model = PublicationNewspaper

    def get(self, request, *args, **kwargs):
        modelobject = self.get_object()
        PubNew = PublicationNewspaper.objects.get(pk=self.kwargs['pk'])
        app = Application.objects.get(pk=PubNew.application.id)
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        if flowcontext["may_update_publication_newspaper"] != "True":
            messages.error(self.request, "Can't delete newspaper publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())
            # Rule: can only delete a condition if the parent application is status
        # 'with referral' or 'with assessor'.
#        if modelobject.application.state not in [Application.APP_STATE_CHOICES.with_assessor, Application.APP_STATE_CHOICES.with_referee]:
 #           messages.warning(self.request, 'You cannot delete this condition')
  #          return HttpResponseRedirect(modelobject.application.get_absolute_url())
        # Rule: can only delete a condition if the request user is an Assessor
        # or they are assigned the referral to which the condition is attached
        # and that referral is not completed.
  #      assessor = Group.objects.get(name='Assessor')
   #     ref = condition.referral
        #    if assessor in self.request.user.groups.all() or (ref and ref.referee == request.user and ref.status == Referral.REFERRAL_STATUS_CHOICES.referred):
        return super(NewsPaperPublicationDelete, self).get(request, *args, **kwargs)
        #    else:
        #       messages.warning(self.request, 'You cannot delete this condition')
        #      return HttpResponseRedirect(condition.application.get_absolute_url())
    def get_success_url(self):
        return reverse('application_detail', args=(self.get_object().application.pk,))
    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
           return HttpResponseRedirect(self.get_success_url())
        # Generate an action.
        modelobject = self.get_object()
        action = Action(
            content_object=modelobject.application, user=self.request.user,
            action='Delete Newspaper Publication {} deleted (status: {})'.format(modelobject.pk, 'delete'))
        action.save()
        messages.success(self.request, 'Newspaper Publication {} has been deleted'.format(modelobject.pk))
        return super(NewsPaperPublicationDelete, self).post(request, *args, **kwargs)
class WebsitePublicationChange(LoginRequiredMixin, CreateView):
    model = PublicationWebsite
    form_class = apps_forms.WebsitePublicationForm
    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_update_publication_website"] != "True":
            messages.error(self.request, "Can't update ebsite publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())
        return super(WebsitePublicationChange, self).get(request, *args, **kwargs)
    def get_success_url(self):
        return reverse('application_detail', args=(self.kwargs['pk'],))

        #    def get_success_url(self):
        #        print self.kwargs['pk']
        #        return reverse('application_detail', args=(self.get_object().application.pk,))
        #        return reverse('application_detail', args=(self.kwargs['pk']))

    def get_context_data(self, **kwargs):
        context = super(WebsitePublicationChange,self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['pk'])
        return context

    def get_initial(self):
        initial = super(WebsitePublicationChange, self).get_initial()
        initial['application'] = self.kwargs['pk']
        #        doc = Record.objects.get(pk=self.kwargs['docid'])
        #        print self.kwargs['docid']      
        #        print PublicationWebsite.objects.get(original_document_id=self.kwargs['docid']) 
        try:
            pub_web = PublicationWebsite.objects.get(original_document_id=self.kwargs['docid'])
        except:
            pub_web = None
        if pub_web:
                initial['published_document'] = pub_web.published_document


                #filelist = [] 
                #if pub_web: 
                #    if pub_web.published_document:
                #        # records = pub_news.records.all()
                #        fileitem = {} 
                #        fileitem['fileid'] = pub_web.published_document.id
                #        fileitem['path'] = pub_web.published_document.upload.name
                #        fileitem['name'] = pub_web.published_document.name
                #        fileitem['short_name'] = pub_web.published_document.upload.name[19:]  
                #        filelist.append(fileitem)

                #if pub_web:
                #    if pub_web.id:
                #        initial['id'] = pub_web.id
                #        print "hello"

                #initial['published_document'] = filelist
                #doc = Record.objects.get(pk=self.kwargs['docid'])
                #initial['original_document'] = doc
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(WebsitePublicationChange, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        forms_data = form.cleaned_data
        self.object = form.save(commit=False)
        pub_web = None
#        print "THE"
        try:
            pub_web = PublicationWebsite.objects.get(original_document_id=self.kwargs['docid'])
        except:
            pub_web = None

        #        if pub_web:
        #            self.object.id = pub_web.id
        #            self.object.published_document = pub_web.published_document

        #            if pub_web.published_document:
        #                if 'published_document-clear_multifileid-' + str(pub_web.published_document.id) in self.request.POST:
        #                    self.object.published_document = None


        orig_doc = Record.objects.get(id=self.kwargs['docid'])
        self.object.original_document = orig_doc
        # print "SSS"
        # print self.request.FILES.get('published_document')
        # print self.request.POST
        if 'published_document_json' in self.request.POST:
            if is_json(self.request.POST['published_document_json']) is True: 
                  json_data = json.loads(self.request.POST['published_document_json'])
                  if 'doc_id' in json_data:
                      try:
                          pub_obj = PublicationWebsite.objects.get(original_document_id=self.kwargs['docid'])                 
                          pub_obj.delete()
                      except: 
                          pass
   
                      new_doc = Record.objects.get(id=json_data['doc_id'])
                      self.object.published_document = new_doc
                  else:
                      pub_obj = PublicationWebsite.objects.get(original_document_id=self.kwargs['docid'])
                      pub_obj.delete()


#             else:
 #                self.object.remove()

     # print json_data
     # self.object.published_document.remove()
    # for d in self.object.published_document.all():
     #    self.object.published_document.remove(d)
     # for i in json_data:
     #    doc = Record.objects.get(id=i['doc_id'])
#             self.object.published_document = i['doc_id']
#             self.object.save()
#        if self.request.FILES.get('published_document'):
#            for f in self.request.FILES.getlist('published_document'):
 #               doc = Record()
  #              doc.upload = f
   #             doc.save()
    #            self.object.published_document = doc
        app = Application.objects.get(pk=self.kwargs['pk'])
        action = Action(
              content_object=app, user=self.request.user, category=Action.ACTION_CATEGORY_CHOICES.change,
        action='Publish New Web Documents for Doc ID: {}'.format(self.kwargs['docid']))
        action.save()
        return super(WebsitePublicationChange, self).form_valid(form)

class FeedbackPublicationCreate(LoginRequiredMixin, CreateView):
    model = PublicationFeedback
    form_class = apps_forms.FeedbackPublicationCreateForm

    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_update_publication_feedback_draft"] == "True":
           return super(FeedbackPublicationCreate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_final"] == "True":
           return super(FeedbackPublicationCreate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_determination"] == "True":
           return super(FeedbackPublicationCreate, self).get(request, *args, **kwargs)
        else:
             messages.error(
                 self.request, "Can't add new newspaper publication to this application")
             return HttpResponseRedirect(app.get_absolute_url())

#        if app.state != app.APP_STATE_CHOICES.draft:
 #           messages.errror(
  #              self.request, "Can't add new feedback publication to this application")
   #         return HttpResponseRedirect(app.get_absolute_url())
#        return super(FeedbackPublicationCreate, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.kwargs['pk'],))

    def get_context_data(self, **kwargs):
        context = super(FeedbackPublicationCreate,
                        self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['pk'])
        return context

    def get_initial(self):
        initial = super(FeedbackPublicationCreate, self).get_initial()
        initial['application'] = self.kwargs['pk']

        if self.kwargs['status'] == 'final':
            initial['status'] = 'final'
        elif self.kwargs['status'] == 'determination':
            initial['status'] = 'determination'
        else:
            initial['status'] = 'draft'
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(FeedbackPublicationCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=True)
#       print self.object.records
        if self.request.FILES.get('records'):
            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)

        return super(FeedbackPublicationCreate, self).form_valid(form)

class FeedbackPublicationView(LoginRequiredMixin, DetailView):
    model = PublicationFeedback
    template_name = 'applications/application_feedback_view.html'

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden Access.')
           return HttpResponseRedirect("/")
        return super(FeedbackPublicationView, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.kwargs['application'],))

    def get_context_data(self, **kwargs):
        context = super(FeedbackPublicationView,
                        self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['application'])
        return context

class FeedbackPublicationUpdate(LoginRequiredMixin, UpdateView):
    model = PublicationFeedback
    form_class = apps_forms.FeedbackPublicationCreateForm

    def get(self, request, *args, **kwargs):
        modelobject = self.get_object()
        app = modelobject.application

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_update_publication_feedback_draft"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_final"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_determination"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        else:
             messages.error(
                 self.request, "Can't change feedback publication for this application")
             return HttpResponseRedirect(app.get_absolute_url())
#        return HttpResponseRedirect(app.get_absolute_url())
        # app = Application.objects.get(pk=self.kwargs['application'])
        # if app.state != app.APP_STATE_CHOICES.draft:
        #    messages.errror(
        #       self.request, "Can't add new newspaper publication to this application")
        #  return HttpResponseRedirect(app.get_absolute_url())
#        return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.kwargs['application'],))

    def get_context_data(self, **kwargs):
        context = super(FeedbackPublicationUpdate,
                        self).get_context_data(**kwargs)
        context['application'] = Application.objects.get(pk=self.kwargs['application'])
        return context

    def get_initial(self):
        initial = super(FeedbackPublicationUpdate, self).get_initial()
        initial['application'] = self.kwargs['application']
        try:
            pub_feed = PublicationFeedback.objects.get(
                pk=self.kwargs['pk'])
        except:
            pub_feed = None

        multifilelist = []
        if pub_feed:
            records = pub_feed.records.all()
            for b1 in records:
                fileitem = {}
                fileitem['fileid'] = b1.id
                fileitem['path'] = b1.upload.name
                multifilelist.append(fileitem)
        initial['records'] = multifilelist
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['application'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(FeedbackPublicationUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        app = Application.objects.get(pk=self.object.application.id)

        pub_feed = PublicationFeedback.objects.get(pk=self.kwargs['pk'])

        records = pub_feed.records.all()
        for filelist in records:
            if 'records-clear_multifileid-' + str(filelist.id) in form.data:
                pub_feed.records.remove(filelist)

        if self.request.FILES.get('records'):
            for f in self.request.FILES.getlist('records'):
                doc = Record()
                doc.upload = f
                doc.save()
                self.object.records.add(doc)

        return super(FeedbackPublicationUpdate, self).form_valid(form)


class FeedbackPublicationDelete(LoginRequiredMixin, DeleteView):
    model = PublicationFeedback

    def get(self, request, *args, **kwargs):
        modelobject = self.get_object()
        app = modelobject.application

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_update_publication_feedback_draft"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_final"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        elif flowcontext["may_update_publication_feedback_determination"] == "True":
           return super(FeedbackPublicationUpdate, self).get(request, *args, **kwargs)
        else:
             messages.error(
                 self.request, "Can't change feedback publication for this application")
             return HttpResponseRedirect(app.get_absolute_url())

        return super(FeedbackPublicationDelete, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.get_object().application.pk,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        # Generate an action.
        modelobject = self.get_object()
        action = Action(
            content_object=modelobject.application, user=self.request.user,
            action='Delete Feedback Publication {} deleted (status: {})'.format(modelobject.pk, 'delete'))
        action.save()
        messages.success(self.request, 'Newspaper Feedback {} has been deleted'.format(modelobject.pk))
        return super(FeedbackPublicationDelete, self).post(request, *args, **kwargs)


class ConditionCreate(LoginRequiredMixin, CreateView):
    """A view for a referee or an internal user to create a Condition object
    on an Application.
    """
    model = Condition
    form_class = apps_forms.ConditionCreateForm

    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])

        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_create_condition"] != "True":
            messages.error(
                self.request, "Can't add new newspaper publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())



        # Rule: conditions can be created when the app is with admin, with
        # referee or with assessor.
        if app.app_type == app.APP_TYPE_CHOICES.emergency:
            if app.state != app.APP_STATE_CHOICES.draft or app.assignee != self.request.user:
                messages.error(
                    self.request, 'New conditions cannot be created for this application!')
                return HttpResponseRedirect(app.get_absolute_url())
        elif app.state not in [app.APP_STATE_CHOICES.with_admin, app.APP_STATE_CHOICES.with_referee, app.APP_STATE_CHOICES.with_assessor]:
            messages.error(
                self.request, 'New conditions cannot be created for this application!')
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ConditionCreate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ConditionCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create a new condition'
        return context

    def get_success_url(self):
        """Override to redirect to the condition's parent application detail view.
        """
        return reverse('application_update', args=(self.object.application.pk,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(ConditionCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        app = Application.objects.get(pk=self.kwargs['pk'])
        self.object = form.save(commit=False)
        self.object.application = app
        # If a referral exists for the parent application for this user,
        # link that to the new condition.
        if Referral.objects.filter(application=app, referee=self.request.user).exists():
            self.object.referral = Referral.objects.get(
                application=app, referee=self.request.user)
        # If the request user is not in the "Referee" group, then assume they're an internal user
        # and set the new condition to "applied" status (default = "proposed").
        referee = Group.objects.get(name='Referee')
        if referee not in self.request.user.groups.all():
            self.object.status = Condition.CONDITION_STATUS_CHOICES.applied
        self.object.save()
        # Record an action on the application:
        action = Action(
            content_object=app, category=Action.ACTION_CATEGORY_CHOICES.create, user=self.request.user,
            action='Created condition {} (status: {})'.format(self.object.pk, self.object.get_status_display()))
        action.save()
        messages.success(self.request, 'Condition {} Created'.format(self.object.pk))

        return super(ConditionCreate, self).form_valid(form)


class ConditionUpdate(LoginRequiredMixin, UpdateView):
    """A view to allow an assessor to update a condition that might have been
    proposed by a referee.
    The ``action`` kwarg is used to define the new state of the condition.
    """
    model = Condition

    def get(self, request, *args, **kwargs):
        condition = self.get_object()

        app = condition.application
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_create_condition"] != "True":
            messages.error(
                self.request, "Can't add new newspaper publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())

        # Rule: can only change a condition if the parent application is status
        # 'with assessor' or 'with_referee' unless it is an emergency works.
        if condition.application.app_type == Application.APP_TYPE_CHOICES.emergency:
            if condition.application.state != Application.APP_STATE_CHOICES.draft:
                messages.error(
                    self.request, 'You can not change conditions when the application has been issued')
                return HttpResponseRedirect(condition.application.get_absolute_url())
            elif condition.application.assignee != self.request.user:
                messages.error(
                    self.request, 'You can not change conditions when the application is not assigned to you')
                return HttpResponseRedirect(condition.application.get_absolute_url())
            else:
                return super(ConditionUpdate, self).get(request, *args, **kwargs)
        elif condition.application.state not in [Application.APP_STATE_CHOICES.with_assessor, Application.APP_STATE_CHOICES.with_referee]:
            messages.error(
                self.request, 'You can only change conditions when the application is "with assessor" or "with referee" status')
            return HttpResponseRedirect(condition.application.get_absolute_url())
        # Rule: can only change a condition if the request user is an Assessor
        # or they are assigned the referral to which the condition is attached
        # and that referral is not completed.
        assessor = Group.objects.get(name='Assessor')
        ref = condition.referral
        if assessor in self.request.user.groups.all() or (ref and ref.referee == request.user and ref.status == Referral.REFERRAL_STATUS_CHOICES.referred):
            return super(ConditionUpdate, self).get(request, *args, **kwargs)
        else:
            messages.warning(self.request, 'You cannot update this condition')
            return HttpResponseRedirect(condition.application.get_absolute_url())

    def get_initial(self):
        initial = super(ConditionUpdate, self).get_initial()
        condition = self.get_object()
#        print condition.application.id
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(condition.application)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(self.request, flowcontext, condition.application.routeid, workflowtype)
        initial['may_assessor_advise'] = flowcontext["may_assessor_advise"]

        initial['assessor_staff'] = False
        if self.request.user.groups.filter(name__in=['Assessor']).exists():
             initial['assessor_staff'] = True
        return initial

    def get_form_class(self):
        # Updating the condition as an 'action' should not allow the user to
        # change the condition text.
        if 'action' in self.kwargs:
            return apps_forms.ConditionActionForm
        return apps_forms.ConditionUpdateForm

    def get_context_data(self, **kwargs):
        context = super(ConditionUpdate, self).get_context_data(**kwargs)
        if 'action' in self.kwargs:
            if self.kwargs['action'] == 'apply':
                context['page_heading'] = 'Apply a proposed condition'
            elif self.kwargs['action'] == 'reject':
                context['page_heading'] = 'Reject a proposed condition'
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(ConditionUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save(commit=False)
        if 'action' in self.kwargs:
            if self.kwargs['action'] == 'apply':
                self.object.status = Condition.CONDITION_STATUS_CHOICES.applied
            elif self.kwargs['action'] == 'reject':
                self.object.status = Condition.CONDITION_STATUS_CHOICES.rejected
            # Generate an action:
            action = Action(
                content_object=self.object.application, user=self.request.user,
                action='Condition {} updated (status: {})'.format(self.object.pk, self.object.get_status_display()))
            action.save()
        self.object.save()
        return HttpResponseRedirect(self.object.application.get_absolute_url()+'')

class ConditionDelete(LoginRequiredMixin, DeleteView):
    model = Condition

    def get(self, request, *args, **kwargs):
        condition = self.get_object()

        app = condition.application
        flow = Flow()
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = {}
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)

        if flowcontext["may_create_condition"] != "True":
            messages.error(
                self.request, "Can't add new newspaper publication to this application")
            return HttpResponseRedirect(app.get_absolute_url())


        # Rule: can only delete a condition if the parent application is status
        # 'with referral' or 'with assessor'. Can also delete if you are the user assigned
        # to an Emergency Works
        if condition.application.app_type != Application.APP_TYPE_CHOICES.emergency:
            if condition.application.state not in [Application.APP_STATE_CHOICES.with_assessor, Application.APP_STATE_CHOICES.with_referee]:
                messages.warning(self.request, 'You cannot delete this condition')
                return HttpResponseRedirect(condition.application.get_absolute_url())
            # Rule: can only delete a condition if the request user is an Assessor
            # or they are assigned the referral to which the condition is attached
            # and that referral is not completed.
            assessor = Group.objects.get(name='Assessor')
            ref = condition.referral
            if assessor in self.request.user.groups.all() or (ref and ref.referee == request.user and ref.status == Referral.REFERRAL_STATUS_CHOICES.referred):
                return super(ConditionDelete, self).get(request, *args, **kwargs)
            else:
                messages.warning(self.request, 'You cannot delete this condition')
                return HttpResponseRedirect(condition.application.get_absolute_url())
        else:
            # Rule: can only delete a condition if the request user is the assignee and the application
            # has not been issued.
            if condition.application.assignee == request.user and condition.application.state != Application.APP_STATE_CHOICES.issued:
                return super(ConditionDelete, self).get(request, *args, **kwargs)
            else:
                messages.warning(self.request, 'You cannot delete this condition')
                return HttpResponseRedirect(condition.application.get_absolute_url())

    def get_success_url(self):
        return reverse('application_detail', args=(self.get_object().application.pk,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        # Generate an action.
        condition = self.get_object()
        action = Action(
            content_object=condition.application, user=self.request.user,
            action='Condition {} deleted (status: {})'.format(condition.pk, condition.get_status_display()))
        action.save()
        messages.success(self.request, 'Condition {} has been deleted'.format(condition.pk))
        return super(ConditionDelete, self).post(request, *args, **kwargs)

class ConditionSuspension(LoginRequiredMixin, UpdateView):
    model = Condition
    form_class = apps_forms.ConditionSuspension

#    def get(self, request, *args, **kwargs):
 #       condition = self.get_object()

        # Rule: can only delete a condition if the parent application is status
        # 'with referral' or 'with assessor'. Can also delete if you are the user assigned
        # to an Emergency Works
#        if condition.application.app_type != Application.APP_TYPE_CHOICES.emergency:
#            if condition.application.state not in [Application.APP_STATE_CHOICES.with_assessor, Application.APP_STATE_CHOICES.with_referee]:
#                messages.warning(self.request, 'You cannot delete this condition')
#                return HttpResponseRedirect(condition.application.get_absolute_url())
#            # Rule: can only delete a condition if the request user is an Assessor
#            # or they are assigned the referral to which the condition is attached
#            # and that referral is not completed.
#            assessor = Group.objects.get(name='Assessor')
#            ref = condition.referral
#            if assessor in self.request.user.groups.all() or (ref and ref.referee == request.user and ref.status == Referral.REFERRAL_STATUS_CHOICES.referred):
#                return super(ConditionDelete, self).get(request, *args, **kwargs)
#            else:
#                messages.warning(self.request, 'You cannot delete this condition')
#                return HttpResponseRedirect(condition.application.get_absolute_url())
#        else:
#            # Rule: can only delete a condition if the request user is the assignee and the application
#            # has not been issued.
#            if condition.application.assignee == request.user and condition.application.state != Application.APP_STATE_CHOICES.issued:
#                return super(ConditionDelete, self).get(request, *args, **kwargs)
#            else:
#                messages.warning(self.request, 'You cannot delete this condition')
#                return HttpResponseRedirect(condition.application.get_absolute_url())

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        else:
           messages.error(self.request, 'Forbidden Access.')
           return HttpResponseRedirect("/")
        return super(FeedbackPublicationView, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_detail', args=(self.get_object().application.pk,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        # Generate an action.
        return super(ConditionSuspension, self).post(request, *args, **kwargs)

    def get_initial(self):
        initial = super(ConditionSuspension, self).get_initial()
        initial['actionkwargs'] = self.kwargs['action']
        return initial

    def form_valid(self, form):

        self.object = form.save(commit=False)

        actionkwargs = self.kwargs['action']
        if actionkwargs == 'suspend':
            self.object.suspend = True
        elif actionkwargs == 'unsuspend':
            self.object.suspend = False

        action = Action(
            content_object=self.object, user=self.request.user,
            action='Condition {} suspend (status: {})'.format(self.object.pk, self.object.get_status_display()))
        action.save()

        messages.success(self.request, 'Condition {} has been suspended'.format(self.object.pk))

        return super(ConditionSuspension, self).form_valid(form)


class VesselCreate(LoginRequiredMixin, CreateView):
    model = Vessel
    form_class = apps_forms.VesselForm

    def get(self, request, *args, **kwargs):
        app = Application.objects.get(pk=self.kwargs['pk'])
#        action = self.kwargs['action']

        flow = Flow()
        flowcontext = {}
        if app.assignee:
           flowcontext['application_assignee_id'] = app.assignee.id
        else:
           flowcontext['application_assignee_id'] = None
       
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)

        if self.request.user.groups.filter(name__in=['Processor']).exists():
            donothing = ''
        elif flowcontext["may_update_vessels_list"] != "True":
#        if app.state != app.APP_STATE_CHOICES.draft:
            messages.error(
                self.request, "Can't add new vessels to this application")
            return HttpResponseRedirect(app.get_absolute_url())
        return super(VesselCreate, self).get(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('application_update', args=(self.kwargs['pk'],))

    def get_context_data(self, **kwargs):
        context = super(VesselCreate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Create new vessel details'
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = Application.objects.get(pk=self.kwargs['pk'])
            return HttpResponseRedirect(app.get_absolute_url())
        return super(VesselCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        app = Application.objects.get(pk=self.kwargs['pk'])
        self.object = form.save()
        app.vessels.add(self.object.id)
        app.save()

        if 'registration_json' in self.request.POST:
             if is_json(self.request.POST['registration_json']) is True:
                 json_data = json.loads(self.request.POST['registration_json'])
                 for d in self.object.registration.all():
                     self.object.registration.remove(d)
                 for i in json_data:
                     doc = Record.objects.get(id=i['doc_id'])
                     self.object.registration.add(doc)

        # Registration document uploads.
#        if self.request.FILES.get('registration'):
#            for f in self.request.FILES.getlist('registration'):
#                doc = Record()
#                doc.upload = f
#                doc.save()
#                self.object.registration.add(doc)

        return super(VesselCreate, self).form_valid(form)


class VesselDelete(LoginRequiredMixin, UpdateView):
    model = Vessel 
    form_class = apps_forms.VesselDeleteForm
    template_name = 'applications/vessel_delete.html'

    def get(self, request, *args, **kwargs):
        vessel = self.get_object()
        app = self.get_object().application_set.first()
        flow = Flow()
        flowcontext = {}
        if app.assignee:
           flowcontext['application_assignee_id'] = app.assignee.id
        else:
           flowcontext['application_assignee_id'] = None

#        flowcontext['application_assignee_id'] = app.assignee.id
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)
        if flowcontext["may_update_vessels_list"] != "True":
#        if app.state != app.APP_STATE_CHOICES.draft:
            messages.error(
                self.request, "Can't add new vessels to this application")
            return HttpResponseRedirect(app.get_absolute_url())
        #if referral.status != Referral.REFERRAL_STATUS_CHOICES.referred:
        #    messages.error(self.request, 'This delete is already completed!')
        #    return HttpResponseRedirect(referral.application.get_absolute_url())
        return super(VesselDelete, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(VesselDelete, self).get_context_data(**kwargs)
        context['vessel'] = self.get_object()
        return context

    def get_success_url(self, application_id):
        return reverse('application_update', args=(application_id,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_object().application.get_absolute_url())
        return super(VesselDelete, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        vessel = self.get_object()
#        application_id = vessel.application.id
        app = self.object.application_set.first()
        vessel.delete()
        # Record an action on the referral's application:
        action = Action(
            content_object=app, user=self.request.user,
            action='Vessel to {} delete'.format(vessel.id))
        action.save()
        return HttpResponseRedirect(self.get_success_url(app.id))

class VesselUpdate(LoginRequiredMixin, UpdateView):
    model = Vessel
    form_class = apps_forms.VesselForm

    def get(self, request, *args, **kwargs):
        app = self.get_object().application_set.first()
        # Rule: can only change a vessel if the parent application is status
        # 'draft'.
        #if app.state != Application.APP_STATE_CHOICES.draft:
        #    messages.error(
        #        self.request, 'You can only change a vessel details when the application is "draft" status')
        #    return HttpResponseRedirect(app.get_absolute_url())
        flowcontext = {}
        if app.assignee:
            flowcontext['application_assignee_id'] = app.assignee.id
        else:
            flowcontext['application_assignee_id'] = None


        flow = Flow()
        #flowcontext = {}
        # flowcontext['application_assignee_id'] = app.assignee.id
        workflowtype = flow.getWorkFlowTypeFromApp(app)
        flow.get(workflowtype)
        DefaultGroups = flow.groupList()
        flowcontext = flow.getAccessRights(request, flowcontext, app.routeid, workflowtype)
        flowcontext = flow.getRequired(flowcontext, app.routeid, workflowtype)
        if flowcontext["may_update_vessels_list"] != "True":
#        if app.state != app.APP_STATE_CHOICES.draft:
            messages.error(
                self.request, "Can't add new vessels to this application")
            return HttpResponseRedirect(app.get_absolute_url())
        return super(VesselUpdate, self).get(request, *args, **kwargs)

    def get_success_url(self,app_id):
        return reverse('application_update', args=(app_id,))

    def get_context_data(self, **kwargs):
        context = super(VesselUpdate, self).get_context_data(**kwargs)
        context['page_heading'] = 'Update vessel details'
        return context

    def get_initial(self):
        initial = super(VesselUpdate, self).get_initial()
#        initial['application_id'] = self.kwargs['pk']
        vessels = self.get_object()
        a1 = vessels.registration.all()
        multifilelist = []
        for b1 in a1:
            fileitem = {}
            fileitem['fileid'] = b1.id
            fileitem['path'] = b1.upload.name
            multifilelist.append(fileitem)
        initial['registration'] = multifilelist

        return initial
    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            app = self.get_object().application_set.first()
            return HttpResponseRedirect(app.get_absolute_url())
        return super(VesselUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.object = form.save()
        # Registration document uploads.
#        rego = self.object.registration.all()

        if 'registration_json' in self.request.POST:
             if is_json(self.request.POST['registration_json']) is True:
                 json_data = json.loads(self.request.POST['registration_json'])
                 for d in self.object.registration.all():
                     self.object.registration.remove(d)
                 for i in json_data:
                     doc = Record.objects.get(id=i['doc_id'])
                     self.object.registration.add(doc)

        #for filelist in rego:
        #    if 'registration-clear_multifileid-' + str(filelist.id) in form.data:
        #         self.object.registration.remove(filelist)

#
#        if self.request.FILES.get('registration'):
#            for f in self.request.FILES.getlist('registration'):
#                doc = Record()
#                doc.upload = f
#                doc.save()
#                self.object.registration.add(doc)

        app = self.object.application_set.first()
        return HttpResponseRedirect(self.get_success_url(app.id),)


#class RecordCreate(LoginRequiredMixin, CreateView):
#    form_class = apps_forms.RecordCreateForm
#    template_name = 'applications/document_form.html'
#
#    def get_context_data(self, **kwargs):
#        context = super(RecordCreate, self).get_context_data(**kwargs)
#        context['page_heading'] = 'Create new Record'
#        return context

#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('home_page'))
#        return super(RecordCreate, self).post(request, *args, **kwargs)
#
#    def form_valid(self, form):
#        """Override form_valid to set the assignee as the object creator.
#        """
#        self.object = form.save(commit=False)
#        self.object.save()
#        success_url = reverse('document_list', args=(self.object.pk,))
#        return HttpResponseRedirect(success_url)


#class RecordList(ListView):
#    model = Record


#class UserAccount(LoginRequiredMixin, DetailView):
#    model = EmailUser
#    template_name = 'accounts/user_account.html'
#
#    def get_object(self, queryset=None):
#        """Override get_object to always return the request user.
#        """
#        return self.request.user
#
#    def get_context_data(self, **kwargs):
#        context = super(UserAccount, self).get_context_data(**kwargs)
#        context['organisations'] = [i.organisation for i in Delegate.objects.filter(email_user=self.request.user)]
#        return context

class UserAccountUpdate(LoginRequiredMixin, UpdateView):
    form_class = apps_forms.EmailUserForm


    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           donothing =""
        elif self.request.user.id == int(self.kwargs['pk']):
           donothing =""
        else:
           messages.error(self.request, 'Forbidden Access.')
           return HttpResponseRedirect("/")
        return super(UserAccountUpdate, self).get(request, *args, **kwargs)

    def get_object(self, queryset=None):
        if 'pk' in self.kwargs:
            if self.request.user.groups.filter(name__in=['Processor']).exists():
               user = EmailUser.objects.get(pk=self.kwargs['pk'])
               return user
            elif self.request.user.id == int(self.kwargs['pk']):
                user = EmailUser.objects.get(pk=self.kwargs['pk'])
                return user
            else:
                messages.error(
                  self.request, "Forbidden Access")
                return HttpResponseRedirect("/")
        else:
            return self.request.user

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('user_account'))
             return HttpResponseRedirect(reverse('person_details_actions', args=(self.kwargs['pk'],'personal')))     
        return super(UserAccountUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        """Override to set first_name and last_name on the EmailUser object.
        """
        self.obj = form.save(commit=False)
        # If identification has been uploaded, then set the id_verified field to None.
        #if 'identification' in data and data['identification']:
        #    self.obj.id_verified = None
        self.obj.save()
#        return HttpResponseRedirect(reverse('user_account'))
        # Record an action on the application:
#        print self.object.all()
#        print serializers.serialize('json', self.object)
#        from django.core import serializers
#        forms_data = form.cleaned_data
#        print serializers.serialize('json', [ forms_data ])

        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.change, user=self.request.user,
            action='Updated Personal Details')
        action.save()
        return HttpResponseRedirect(reverse('person_details_actions', args=(self.obj.pk,'personal')))

class UserAccountIdentificationUpdate(LoginRequiredMixin, UpdateView):
    form_class = apps_forms.UserFormIdentificationUpdate
    #form_class = apps_forms.OrganisationCertificateForm

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = self.get_organisation()

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
           pass
        else:
           if admin_staff is True:
               return super(UserAccountIdentificationUpdate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised to view this organisation.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(UserAccountIdentificationUpdate, self).get(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        if admin_staff == True:
           return super(UserAccountIdentificationUpdate, self).get(request, *args, **kwargs)
        elif self.request.user.id == int(self.kwargs['pk']):
           return super(UserAccountIdentificationUpdate, self).get(request, *args, **kwargs) 
        else:
           messages.error(self.request, 'Forbidden Access.')
        return HttpResponseRedirect("/")
 
    def get_object(self, queryset=None):
        if 'pk' in self.kwargs:
            if self.request.user.groups.filter(name__in=['Processor']).exists():
               user = EmailUser.objects.get(pk=self.kwargs['pk'])
               return user
            else:
                messages.error(
                  self.request, "Forbidden Access")
                return HttpResponseRedirect("/")
        else:
            return self.request.user

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('user_account'))
        return super(UserAccountIdentificationUpdate, self).post(request, *args, **kwargs)

    def get_initial(self):
        initial = super(UserAccountIdentificationUpdate, self).get_initial()
        emailuser = self.get_object()

        if emailuser.identification:
           initial['identification'] = emailuser.identification.file
        return initial

    def form_valid(self, form):
        """Override to set first_name and last_name on the EmailUser object.
        """
        self.obj = form.save(commit=False)
        forms_data = form.cleaned_data

        # If identification has been uploaded, then set the id_verified field to None.
        # if 'identification' in data and data['identification']:
        #    self.obj.id_verified = None
        if self.request.POST.get('identification-clear'):
            self.obj.identification = None

        if self.request.FILES.get('identification'):
            if Attachment_Extension_Check('single', forms_data['identification'], None) is False:
                raise ValidationError('Identification contains and unallowed attachment extension.')
            new_doc = Document()
            new_doc.file = self.request.FILES['identification']
            new_doc.save()
            self.obj.identification = new_doc

        self.obj.save()

        action = Action(
            content_object=self.object, category=Action.ACTION_CATEGORY_CHOICES.change, user=self.request.user,
            action='Updated Identification')
        action.save()

        return HttpResponseRedirect(reverse('person_details_actions', args=(self.obj.pk,'identification')))


class OrganisationCertificateUpdate(LoginRequiredMixin, UpdateView):
    model = OrganisationExtras
    form_class = apps_forms.OrganisationCertificateForm

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org_extras = self.get_object()
        org =org_extras.organisation

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
            pass
        else:
           if admin_staff is True:
               return super(OrganisationCertificateUpdate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationCertificateUpdate, self).get(request, *args, **kwargs)

#    def get_object(self, queryset=None):
#        if 'pk' in self.kwargs:
#            if self.request.user.groups.filter(name__in=['Processor']).exists():
#                #user = EmailUser.objects.get(pk=self.kwargs['pk'])
#               return self 
#            else:
#                messages.error(
#                  self.request, "Forbidden Access")
#                return HttpResponseRedirect("/")
#        else:
#            return self.request.user

    def post(self, request, *args, **kwargs):
        if 'identification' in request.FILES:
            if Attachment_Extension_Check('single', request.FILES['identification'], ['.pdf','.png','.jpg']) is False:
               messages.error(self.request,'You have added and unallowed attachment extension.')
               return HttpResponseRedirect(request.path)


        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.kwargs['pk'],'certofincorp')))
        return super(OrganisationCertificateUpdate, self).post(request, *args, **kwargs)

    def get_initial(self):
        initial = super(OrganisationCertificateUpdate, self).get_initial()
        org = self.get_object()
        #print org.identification
        if self.object.identification:
           initial['identification'] = self.object.identification.upload
           
        return initial

    def form_valid(self, form):
        """Override to set first_name and last_name on the EmailUser object.
        """
        self.obj = form.save(commit=False)
        forms_data = form.cleaned_data

        # If identification has been uploaded, then set the id_verified field to None.
        # if 'identification' in data and data['identification']:
        #    self.obj.id_verified = None
        if self.request.POST.get('identification-clear'):
            self.obj.identification = None

        if self.request.FILES.get('identification'):
            if Attachment_Extension_Check('single', forms_data['identification'], ['.pdf','.png','.jpg']) is False:
                raise ValidationError('Identification contains and unallowed attachment extension.')
            new_doc = Record()
            new_doc.upload = self.request.FILES['identification']
            new_doc.save()
            self.obj.identification = new_doc

        self.obj.save()
        return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.obj.organisation.pk,'certofincorp')))

class AddressCreate(LoginRequiredMixin, CreateView):
    """A view to create a new address for an EmailUser.
    """
    form_class = apps_forms.AddressForm
    template_name = 'accounts/address_form.html'

    def get(self, request, *args, **kwargs):
#        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        self.object = EmailUser.objects.get(id=self.kwargs['userid']) 
#
        if admin_staff is True:
             return super(AddressCreate, self).get(request, *args, **kwargs)
        elif request.user == self.object:
             return super(AddressCreate, self).get(request, *args, **kwargs)
        else:
             messages.error(self.request, 'You are not authorised to view.')
        return HttpResponseRedirect(reverse('home_page'))
#        return super(AddressCreate, self).get(request, *args, **kwargs)

    def dispatch(self, request, *args, **kwargs):
        # Rule: the ``type`` kwarg must be 'postal' or 'billing'
        if self.kwargs['type'] not in ['postal', 'billing']:
            messages.error(self.request, 'Invalid address type!')
            return HttpResponseRedirect(reverse('user_account'))
        return super(AddressCreate, self).dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(AddressCreate, self).get_context_data(**kwargs)
        context['address_type'] = self.kwargs['type']
        context['action'] = 'Create'
        if 'userid' in self.kwargs:
            user = EmailUser.objects.get(id=self.kwargs['userid'])
            context['principal'] = user.email
        else:
            context['principal'] = self.request.user.email
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('user_account'))
        return super(AddressCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        if 'userid' in self.kwargs:
            u = EmailUser.objects.get(id=self.kwargs['userid'])
        else:
            u = self.request.user

        self.obj = form.save(commit=False)
        self.obj.user = u
        self.obj.save()
        # Attach the new address to the user's profile.
        if self.kwargs['type'] == 'postal':
            u.postal_address = self.obj
        elif self.kwargs['type'] == 'billing':
            u.billing_address = self.obj
        u.save()

#        if 'userid' in self.kwargs:
            #    if self.request.user.is_staff is True:
        action = Action(
           content_object=u, category=Action.ACTION_CATEGORY_CHOICES.change, user=self.request.user,
           action='New '+self.kwargs['type']+' address created')
        action.save()

        return HttpResponseRedirect(reverse('person_details_actions', args=(u.id,'address')))
        #    else:
        #        return HttpResponseRedirect(reverse('user_account'))
 #       else:
  #          return HttpResponseRedirect(reverse('user_account'))

class AddressUpdate(LoginRequiredMixin, UpdateView):
    model = Address
    form_class = apps_forms.AddressForm
    success_url = reverse_lazy('user_account')


    def get(self, request, *args, **kwargs):
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        address = self.get_object()
        u = request.user
        # User addresses: only the user can change an address.
        if u.postal_address == address or u.billing_address == address:
            return super(AddressUpdate, self).get(request, *args, **kwargs)
        
        # Organisational addresses: find which org uses this address, and if
        # the user is a delegate for that org then they can change it.
        org_list = list(chain(address.org_postal_address.all(), address.org_billing_address.all()))
        if Delegate.objects.filter(email_user=u, organisation__in=org_list).exists():
            return super(AddressUpdate, self).get(request, *args, **kwargs)
#        elif u.is_staff is True: 
        elif admin_staff is True:
            return super(AddressUpdate, self).get(request, *args, **kwargs)
        else:
            messages.error(self.request, 'You cannot update this address!')
            return HttpResponseRedirect(reverse('home_page'))

    def get_context_data(self, **kwargs):
        context = super(AddressUpdate, self).get_context_data(**kwargs)
        context['action'] = 'Update'
        address = self.get_object()
        u = self.request.user
        if u.postal_address == address:
            context['action'] = 'Update postal'
            context['principal'] = u.email
        if u.billing_address == address:
            context['action'] = 'Update billing'
            context['principal'] = u.email
        # TODO: include context for Organisation addresses.
        return context

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            #return HttpResponseRedirect(self.success_url)
            obj = self.get_object()
            u = obj.user
            
            if 'org_id' in self.kwargs:
                return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.kwargs['org_id'],'address')))
            else:
                return HttpResponseRedirect(reverse('person_details_actions', args=(u.id,'address')))
        #if self.request.user.is_staff is True:
        #    obj = self.get_object()
        #    u = obj.user
        #    return HttpResponseRedirect(reverse('person_details_actions', args=(u.id,'address')))
        #else:
        return super(AddressUpdate, self).post(request, *args, **kwargs)


    def form_valid(self, form):
        self.obj = form.save()
        obj = self.get_object()
        u = obj.user
        if 'org_id' in self.kwargs:
            org =Organisation.objects.get(id= self.kwargs['org_id'])
            action = Action(
                content_object=org, category=Action.ACTION_CATEGORY_CHOICES.change, user=self.request.user,
                action='Organisation address updated')
            action.save()
            return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.kwargs['org_id'],'address')))

        else:
            action = Action(
                content_object=u, category=Action.ACTION_CATEGORY_CHOICES.change, user=self.request.user,
                action='Person address updated')
            action.save()

            return HttpResponseRedirect(reverse('person_details_actions', args=(u.id,'address')))


#class AddressDelete(LoginRequiredMixin, DeleteView):
#    """A view to allow the deletion of an address. Not currently in use,
#    because the ledge Address model can cause the linked EmailUser object to
#    be deleted along with the Address object :/
#    """
#    model = Address
#    success_url = reverse_lazy('user_account')
#
#    def get(self, request, *args, **kwargs):
#        address = self.get_object()
#        u = self.request.user
#        delete_address = False
#        # Rule: only the address owner can delete an address.
#        if u.postal_address == address or u.billing_address == address:
#            delete_address = True
#        # Organisational addresses: find which org uses this address, and if
#        # the user is a delegate for that org then they can delete it.
#        #org_list = list(chain(address.org_postal_address.all(), address.org_billing_address.all()))
#        #for org in org_list:
#        #    if profile in org.delegates.all():
#        #        delete_address = True
#        if delete_address:
#            return super(AddressDelete, self).get(request, *args, **kwargs)
#        else:
#            messages.error(self.request, 'You cannot delete this address!')
#            return HttpResponseRedirect(self.success_url)
#
#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(self.success_url)
#        return super(AddressDelete, self).post(request, *args, **kwargs)


#class OrganisationList(LoginRequiredMixin, ListView):
#    model = Organisation
#
#    def get_queryset(self):
#        qs = super(OrganisationList, self).get_queryset()
#        # Did we pass in a search string? If so, filter the queryset and return it.
#        if 'q' in self.request.GET and self.request.GET['q']:
#            query_str = self.request.GET['q']
#            # Replace single-quotes with double-quotes
#            query_str = query_str.replace("'", r'"')
#            # Filter by name and ABN fields.
#            query = get_query(query_str, ['name', 'abn'])
#            qs = qs.filter(query).distinct()
#        return qs

class PersonDetails(LoginRequiredMixin, DetailView):
    model = EmailUser 
    template_name = 'applications/person_details.html'

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        self.object = self.get_object()

        if admin_staff is True:
             return super(PersonDetails, self).get(request, *args, **kwargs)
        elif request.user == self.object:
             return super(PersonDetails, self).get(request, *args, **kwargs)
        else:
               messages.error(self.request, 'You are not authorised to view.')
        return HttpResponseRedirect(reverse('home_page'))


    def get_queryset(self):
        qs = super(PersonDetails, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by name and ABN fields.
            query = get_query(query_str, ['name', 'abn'])
            qs = qs.filter(query).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(PersonDetails, self).get_context_data(**kwargs)
        org = self.get_object()
#        context['user_is_delegate'] = Delegate.objects.filter(email_user=self.request.user, organisation=org).exists()
        context['nav_details'] = 'active'

        if "action" in self.kwargs:
             action=self.kwargs['action']
             # Navbar
             if action == "personal":
                 context['nav_details_personal'] = "active"
             elif action == "identification":
                 context['nav_details_identification'] = "active"
                 #context['person'] = EmailUser.objects.get(id=self.kwargs['pk'])
                 

             elif action == "address":
                 context['nav_details_address'] = "active"
             elif action == "contactdetails":
                 context['nav_details_contactdetails'] = "active"
             elif action == "companies":
                 context['nav_details_companies'] = "active"
                 user = EmailUser.objects.get(id=self.kwargs['pk'])
                 context['organisations'] = Delegate.objects.filter(email_user=user)
#                 for i in context['organisations']:
 #                    print i.organisation.name
                 #print context['organisations']

        return context

#class PersonOrgDelete(LoginRequiredMixin, UpdateView):
#    model = Organisation 
#    form_class = apps_forms.PersonOrgDeleteForm
#    template_name = 'applications/referral_delete.html'
#
#    def get(self, request, *args, **kwargs):
#        referral = self.get_object()
#        return super(PersonOrgDelete, self).get(request, *args, **kwargs)
#
#    def get_success_url(self, org_id):
#        return reverse('person_details_actions', args=(org_id,'companies'))
#
#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('person_details_actions', args=(self.kwargs['pk'],'companies')))
#        return super(PersonOrgDelete, self).post(request, *args, **kwargs)
#
#    def form_valid(self, form):
#        org = self.get_object()
#        org_id = org.id
#        org.delete()
#        # Record an action on the referral's application:
#        action = Action(
#            content_object=ref.application, user=self.request.user,
#            action='Organisation {} deleted'.format(org_id))
#        action.save()
#        return HttpResponseRedirect(self.get_success_url(self.pk))

class PersonOther(LoginRequiredMixin, DetailView):
    model = EmailUser
    template_name = 'applications/person_details.html'

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        self.object = self.get_object()

        if admin_staff is True:
             return super(PersonOther, self).get(request, *args, **kwargs)
        elif request.user == self.object:
             return super(PersonOther, self).get(request, *args, **kwargs)
        else:
               messages.error(self.request, 'You are not authorised')
        return HttpResponseRedirect(reverse('home_page'))

#    def get_queryset(self):
#        qs = super(PersonOther, self).get_queryset()
#        # Did we pass in a search string? If so, filter the queryset and return it.
#        if 'q' in self.request.GET and self.request.GET['q']:
#            query_str = self.request.GET['q']
#            # Replace single-quotes with double-quotes
#            query_str = query_str.replace("'", r'"')
#            # Filter by name and ABN fields.
#            query = get_query(query_str, ['name', 'abn'])
#            qs = qs.filter(query).distinct()
        #print self.template_name
#        return qs

    def get_context_data(self, **kwargs):
        context = super(PersonOther, self).get_context_data(**kwargs)

        org = self.get_object()
#       context['user_is_delegate'] = Delegate.objects.filter(email_user=self.request.user, organisation=org).exists()
        context['nav_other'] = 'active'

        if "action" in self.kwargs:
             action=self.kwargs['action']
             # Navbar
             if action == "applications":
                 user = EmailUser.objects.get(id=self.kwargs['pk'])
                 delegate = Delegate.objects.filter(email_user=user).values('organisation__id')

                 context['nav_other_applications'] = "active"
                 context['app'] = ''

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
                 for i in Application.APP_TYPE_CHOICES:
                     if i[0] in [4,5,6,7,8,9,10,11]:
                         skip = 'yes'
                     else:
                         APP_TYPE_CHOICES.append(i)
                         APP_TYPE_CHOICES_IDS.append(i[0])
                 context['app_apptypes'] = APP_TYPE_CHOICES

                 context['app_appstatus'] = list(Application.APP_STATE_CHOICES)
                 search_filter = Q(applicant=self.kwargs['pk']) | Q(organisation__in=delegate)
                 if 'searchaction' in self.request.GET and self.request.GET['searchaction']:
                      query_str = self.request.GET['q']
                   #   query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str)
                      if self.request.GET['apptype'] != '':
                          search_filter &= Q(app_type=int(self.request.GET['apptype']))
                      else:
                          end = ''
                          # search_filter &= Q(app_type__in=APP_TYPE_CHOICES_IDS)


                      if self.request.GET['appstatus'] != '':
                          search_filter &= Q(state=int(self.request.GET['appstatus']))

#                      applications = Application.objects.filter(query_obj)
                      context['query_string'] = self.request.GET['q']

                      if self.request.GET['apptype'] != '':
                          context['apptype'] = int(self.request.GET['apptype'])
                      if 'appstatus' in self.request.GET:
                          if self.request.GET['appstatus'] != '':
                              context['appstatus'] = int(self.request.GET['appstatus'])

                      if 'q' in self.request.GET and self.request.GET['q']:
                          query_str = self.request.GET['q']
                          query_str_split = query_str.split()
                          for se_wo in query_str_split:
                              search_filter &= Q(pk__contains=se_wo) | Q(title__contains=se_wo)

#                 print Q(Q(state__in=APP_TYPE_CHOICES_IDS) & Q(search_filter)) 
                 applications = Application.objects.filter(Q(app_type__in=APP_TYPE_CHOICES_IDS) & Q(search_filter) )[:200]

                 usergroups = self.request.user.groups.all()
                 context['app_list'] = []

                 for app in applications:
                      row = {}
                      row['may_assign_to_person'] = 'False'
                      row['app'] = app

                      # Create a distinct list of applicants
#                      if app.applicant:
#                          if app.applicant.id in context['app_applicants']:
#                               donothing = ''
#                          else:
#                              context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
#                              context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name  })
                          # end of creation

                      if app.group is not None:
                          if app.group in usergroups:
                              row['may_assign_to_person'] = 'True'
                      context['app_list'].append(row)

             elif action == "approvals":
                 context['nav_other_approvals'] = "active"
                 user = EmailUser.objects.get(id=self.kwargs['pk'])
                 delegate = Delegate.objects.filter(email_user=user).values('id')

                 search_filter = Q(applicant=self.kwargs['pk'], status=1 ) | Q(organisation__in=delegate)

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
                 for i in Application.APP_TYPE_CHOICES:
                     if i[0] in [4,5,6,7,8,9,10,11]:
                          skip = 'yes'
                     else:
                          APP_TYPE_CHOICES.append(i)
                          APP_TYPE_CHOICES_IDS.append(i[0])
                 context['app_apptypes']= APP_TYPE_CHOICES


                 if 'action' in self.request.GET and self.request.GET['action']:
#                    query_str = self.request.GET['q']
#                    search_filter = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str)

                    if self.request.GET['apptype'] != '':
                        search_filter &= Q(app_type=int(self.request.GET['apptype']))
                    else:
                        search_filter &= Q(app_type__in=APP_TYPE_CHOICES_IDS)
 
                    if self.request.GET['appstatus'] != '':
                        search_filter &= Q(status=int(self.request.GET['appstatus']))

                    context['query_string'] = self.request.GET['q']

                    if self.request.GET['apptype'] != '':
                        context['apptype'] = int(self.request.GET['apptype'])
                    if 'appstatus' in self.request.GET:
                        if self.request.GET['appstatus'] != '':
                            context['appstatus'] = int(self.request.GET['appstatus'])

                    if 'q' in self.request.GET and self.request.GET['q']:
                       query_str = self.request.GET['q']
                       query_str_split = query_str.split()
                       for se_wo in query_str_split:
                           search_filter= Q(pk__contains=se_wo) | Q(title__contains=se_wo)
                 approval = Approval.objects.filter(search_filter)[:200]

                 context['app_list'] = []
                 context['app_applicants'] = {}
                 context['app_applicants_list'] = []
                 context['app_appstatus'] = list(Approval.APPROVAL_STATE_CHOICES)

                 for app in approval:
                     row = {}
                     row['app'] = app
                     if app.applicant:
                         if app.applicant.id in context['app_applicants']:
                             donothing = ''
                         else:
                             context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
                             context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name})

                     context['app_list'].append(row)

             elif action == "emergency":
                 context['nav_other_emergency'] = "active"
                 action=self.kwargs['action']
             # Navbar
                 context['app'] = ''

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
#                 for i in Application.APP_TYPE_CHOICES:
                     #                     if i[0] in [4,5,6,7,8,9,10,11]:
                         #                         skip = 'yes'
#                     else:
                         #                         APP_TYPE_CHOICES.append(i)
#                         APP_TYPE_CHOICES_IDS.append(i[0])

                 APP_TYPE_CHOICES.append('4')
                 APP_TYPE_CHOICES_IDS.append('4')
                 context['app_apptypes']= APP_TYPE_CHOICES

                 context['app_appstatus'] = list(Application.APP_STATE_CHOICES)
                 user = EmailUser.objects.get(id=self.kwargs['pk'])
                 delegate = Delegate.objects.filter(email_user=user).values('id')

                 search_filter = Q(applicant=self.kwargs['pk'], app_type=4) | Q(organisation__in=delegate)

                 if 'searchaction' in self.request.GET and self.request.GET['searchaction']:
                      query_str = self.request.GET['q']
                   #   query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str)

                      context['query_string'] = self.request.GET['q']

                      if self.request.GET['appstatus'] != '':
                          search_filter &= Q(state=int(self.request.GET['appstatus']))


                      if 'appstatus' in self.request.GET:
                          if self.request.GET['appstatus'] != '':
                              context['appstatus'] = int(self.request.GET['appstatus'])


                      if 'q' in self.request.GET and self.request.GET['q']:
                          query_str = self.request.GET['q']
                          query_str_split = query_str.split()
                          for se_wo in query_str_split:
                              search_filter= Q(pk__contains=se_wo) | Q(title__contains=se_wo)
               
                 applications = Application.objects.filter(search_filter)[:200]

#                print applications
                 usergroups = self.request.user.groups.all()
                 context['app_list'] = []
                 for app in applications:
                      row = {}
                      row['may_assign_to_person'] = 'False'
                      row['app'] = app

                      # Create a distinct list of applicants
#                      if app.applicant:
#                          if app.applicant.id in context['app_applicants']:
#                               donothing = ''
#                          else:
#                              context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
#                              context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name  })
                          # end of creation

                      if app.group is not None:
                          if app.group in usergroups:
                              row['may_assign_to_person'] = 'True'
                      context['app_list'].append(row)

             elif action == "clearance":
                 context['nav_other_clearance'] = "active"
                 if 'q' in self.request.GET and self.request.GET['q']:
                      context['query_string'] = self.request.GET['q']

                 user = EmailUser.objects.get(id=self.kwargs['pk'])
                 delegate = Delegate.objects.filter(email_user=user).values('id')
                 search_filter = Q(applicant=self.kwargs['pk']) | Q(organisation__in=delegate)

                 items = Compliance.objects.filter(applicant=self.kwargs['pk']).order_by('due_date')

                 context['app_applicants'] = {}
                 context['app_applicants_list'] = []
                 context['app_apptypes'] = list(Application.APP_TYPE_CHOICES)

                 APP_STATUS_CHOICES = []
                 for i in Application.APP_STATE_CHOICES:
                     if i[0] in [1,11,16]:
                         APP_STATUS_CHOICES.append(i)

                 context['app_appstatus'] = list(APP_STATUS_CHOICES)
                 context['compliance'] = items

                 #if 'action' in self.request.GET and self.request.GET['action']:
                 #     query_str = self.request.GET['q']
                 #     query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(assignee__email__icontains=query_str)
                 #     query_obj &= Q(app_type=4)

                 #     if self.request.GET['applicant'] != '':
                 #         query_obj &= Q(applicant=int(self.request.GET['applicant']))
                 #     if self.request.GET['appstatus'] != '':
                 #         query_obj &= Q(state=int(self.request.GET['appstatus']))

                 #     applications = Compliance.objects.filter(query_obj)
                 #     context['query_string'] = self.request.GET['q']

                 #if 'applicant' in self.request.GET:
                 #     if self.request.GET['applicant'] != '':
                 #         context['applicant'] = int(self.request.GET['applicant'])
                 #if 'appstatus' in self.request.GET:
                 #     if self.request.GET['appstatus'] != '':
                 #         context['appstatus'] = int(self.request.GET['appstatus'])
 
                 #usergroups = self.request.user.groups.all()
                 #context['app_list'] = []
                 #for item in items:
                 #     row = {}
                 #     row['may_assign_to_person'] = 'False'
                 #     row['app'] = item
                 #context['may_create'] = True
                 #processor = Group.objects.get(name='Processor')
                 # Rule: admin officers may self-assign applications.
                 #if processor in self.request.user.groups.all() or self.request.user.is_superuser:
                 #    context['may_assign_processor'] = True

        return context

class OrganisationDetails(LoginRequiredMixin, DetailView):
    model = Organisation
    template_name = 'applications/organisation_details.html'

    def get_organisation(self):
        return Organisation.objects.get(pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = self.get_organisation()

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
           donothing = ""
        else:
           if admin_staff is True:
               return super(OrganisationDetails, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised to view this organisation.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationDetails, self).get(request, *args, **kwargs)


    def get_queryset(self):
        qs = super(OrganisationDetails, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by name and ABN fields.
            query = get_query(query_str, ['name', 'abn'])
            qs = qs.filter(query).distinct()
        return qs

    def get_context_data(self, **kwargs):
        context = super(OrganisationDetails, self).get_context_data(**kwargs)
        org = self.get_object()
        context['user_is_delegate'] = Delegate.objects.filter(email_user=self.request.user, organisation=org).exists()
        context['nav_details'] = 'active'

        if "action" in self.kwargs:
             action=self.kwargs['action']
             # Navbar
             if action == "company":
                 context['nav_details_company'] = "active"
             elif action == "certofincorp":
                 context['nav_details_certofincorp'] = "active"
                 org = Organisation.objects.get(id=self.kwargs['pk'])
                 if OrganisationExtras.objects.filter(organisation=org.id).exists():
                     context['org_extras'] = OrganisationExtras.objects.get(organisation=org.id)
                 context['org'] = org
             elif action == "address":
                 context['nav_details_address'] = "active"
             elif action == "contactdetails":
                 context['nav_details_contactdetails'] = "active"
                 org = Organisation.objects.get(id=self.kwargs['pk'])
                 context['organisation_contacts'] = OrganisationContact.objects.filter(organisation=org)
             elif action == "linkedperson":
                 context['nav_details_linkedperson'] = "active"
                 org = Organisation.objects.get(id=self.kwargs['pk'])
                 context['linkedpersons'] = Delegate.objects.filter(organisation=org)
                 if OrganisationExtras.objects.filter(organisation=org.id).exists():
                    context['org_extras'] = OrganisationExtras.objects.get(organisation=org.id)

        return context


class OrganisationOther(LoginRequiredMixin, DetailView):
    model = Organisation
    template_name = 'applications/organisation_details.html'

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = self.get_object()

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
           donothing = ""
        else:
           if admin_staff is True:
               return super(OrganisationOther, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised to view this organisation.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationOther, self).get(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(OrganisationOther, self).get_queryset()
        # Did we pass in a search string? If so, filter the queryset and return it.
        if 'q' in self.request.GET and self.request.GET['q']:
            query_str = self.request.GET['q']
            # Replace single-quotes with double-quotes
            query_str = query_str.replace("'", r'"')
            # Filter by name and ABN fields.
            query = get_query(query_str, ['name', 'abn'])
            qs = qs.filter(query).distinct()
        #print self.template_name
        return qs

    def get_context_data(self, **kwargs):
        context = super(OrganisationOther, self).get_context_data(**kwargs)
        org = self.get_object()
        context['user_is_delegate'] = Delegate.objects.filter(email_user=self.request.user, organisation=org).exists()
        context['nav_other'] = 'active'

        if "action" in self.kwargs:
             action=self.kwargs['action']

             # Navbar
             if action == "applications":
                 context['nav_other_applications'] = "active"
                 context['app'] = ''

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
                 for i in Application.APP_TYPE_CHOICES:
                     if i[0] in [4,5,6,7,8,9,10,11]:
                         skip = 'yes'
                     else:
                         APP_TYPE_CHOICES.append(i)
                         APP_TYPE_CHOICES_IDS.append(i[0])
                 context['app_apptypes'] = APP_TYPE_CHOICES

                 context['app_appstatus'] = list(Application.APP_STATE_CHOICES)
                 search_filter = Q(organisation=self.kwargs['pk'])
                 
                 if 'searchaction' in self.request.GET and self.request.GET['searchaction']:
                      query_str = self.request.GET['q']
                   #   query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str)

                      if self.request.GET['apptype'] != '':
                          search_filter &= Q(app_type=int(self.request.GET['apptype']))
                      else:
                          end = ''
                          # search_filter &= Q(app_type__in=APP_TYPE_CHOICES_IDS)


                      if self.request.GET['appstatus'] != '':
                          search_filter &= Q(state=int(self.request.GET['appstatus']))

#                      applications = Application.objects.filter(query_obj)
                      context['query_string'] = self.request.GET['q']

                      if self.request.GET['apptype'] != '':
                          context['apptype'] = int(self.request.GET['apptype'])
                      if 'appstatus' in self.request.GET:
                          if self.request.GET['appstatus'] != '':
                              context['appstatus'] = int(self.request.GET['appstatus'])

                      if 'q' in self.request.GET and self.request.GET['q']:
                          query_str = self.request.GET['q']
                          query_str_split = query_str.split()
                          for se_wo in query_str_split:
                              search_filter = Q(pk__contains=se_wo) | Q(title__contains=se_wo)
                 applications = Application.objects.filter(search_filter)[:200]
                 usergroups = self.request.user.groups.all()
                 context['app_list'] = []

                 for app in applications:
                      row = {}
                      row['may_assign_to_person'] = 'False'
                      row['app'] = app

                      if app.group is not None:
                          if app.group in usergroups:
                              row['may_assign_to_person'] = 'True'
                      context['app_list'].append(row)

             elif action == "approvals":
                 context['nav_other_approvals'] = "active"
                 search_filter = Q(organisation__in=self.kwargs['pk'], status=1)

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
                 for i in Application.APP_TYPE_CHOICES:
                     if i[0] in [4,5,6,7,8,9,10,11]:
                          skip = 'yes'
                     else:
                          APP_TYPE_CHOICES.append(i)
                          APP_TYPE_CHOICES_IDS.append(i[0])
                 context['app_apptypes']= APP_TYPE_CHOICES


                 if 'action' in self.request.GET and self.request.GET['action']:
#                    query_str = self.request.GET['q']
#                    search_filter = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str)

                    if self.request.GET['apptype'] != '':
                        search_filter &= Q(app_type=int(self.request.GET['apptype']))
                    else:
                        search_filter &= Q(app_type__in=APP_TYPE_CHOICES_IDS)

                    if self.request.GET['appstatus'] != '':
                        search_filter &= Q(status=int(self.request.GET['appstatus']))

                    context['query_string'] = self.request.GET['q']

                    if self.request.GET['apptype'] != '':
                        context['apptype'] = int(self.request.GET['apptype'])
                    if 'appstatus' in self.request.GET:
                        if self.request.GET['appstatus'] != '':
                            context['appstatus'] = int(self.request.GET['appstatus'])

                    if 'q' in self.request.GET and self.request.GET['q']:
                       query_str = self.request.GET['q']
                       query_str_split = query_str.split()
                       for se_wo in query_str_split:
                           search_filter= Q(pk__contains=se_wo) | Q(title__contains=se_wo)
                 approval = Approval.objects.filter(search_filter)[:200]

                 context['app_list'] = []
                 context['app_applicants'] = {}
                 context['app_applicants_list'] = []
                 context['app_appstatus'] = list(Approval.APPROVAL_STATE_CHOICES)
                 for app in approval:
                     row = {}
                     row['app'] = app
                     if app.applicant:
                         if app.applicant.id in context['app_applicants']:
                             donothing = ''
                         else:
                             context['app_applicants'][app.applicant.id] = app.applicant.first_name + ' ' + app.applicant.last_name
                             context['app_applicants_list'].append({"id": app.applicant.id, "name": app.applicant.first_name + ' ' + app.applicant.last_name})

                     context['app_list'].append(row)

             elif action == "emergency":
                 context['nav_other_emergency'] = "active"
                 action=self.kwargs['action']
                 context['app'] = ''

                 APP_TYPE_CHOICES = []
                 APP_TYPE_CHOICES_IDS = []
                 APP_TYPE_CHOICES.append('4')
                 APP_TYPE_CHOICES_IDS.append('4')
                 context['app_apptypes']= APP_TYPE_CHOICES
                 context['app_appstatus'] = list(Application.APP_STATE_CHOICES)
                 #user = EmailUser.objects.get(id=self.kwargs['pk'])
                 #delegate = Delegate.objects.filter(email_user=user).values('id')
                 search_filter = Q(organisation=self.kwargs['pk'], app_type=4)

                 if 'searchaction' in self.request.GET and self.request.GET['searchaction']:
                      query_str = self.request.GET['q']
                   #   query_obj = Q(pk__contains=query_str) | Q(title__icontains=query_str) | Q(applicant__email__icontains=query_str) | Q(organisation__name__icontains=query_str) | Q(assignee__email__icontains=query_str)

                      context['query_string'] = self.request.GET['q']

                      if self.request.GET['appstatus'] != '':
                          search_filter &= Q(state=int(self.request.GET['appstatus']))


                      if 'appstatus' in self.request.GET:
                          if self.request.GET['appstatus'] != '':
                              context['appstatus'] = int(self.request.GET['appstatus'])


                      if 'q' in self.request.GET and self.request.GET['q']:
                          query_str = self.request.GET['q']
                          query_str_split = query_str.split()
                          for se_wo in query_str_split:
                              search_filter= Q(pk__contains=se_wo) | Q(title__contains=se_wo)

                 applications = Application.objects.filter(search_filter)[:200]

#                print applications
                 usergroups = self.request.user.groups.all()
                 context['app_list'] = []
                 for app in applications:
                      row = {}
                      row['may_assign_to_person'] = 'False'
                      row['app'] = app

                      if app.group is not None:
                          if app.group in usergroups:
                              row['may_assign_to_person'] = 'True'
                      context['app_list'].append(row)

             elif action == "clearance":
                 context['nav_other_clearance'] = "active"
                 context['query_string'] = ''

                 if 'q' in self.request.GET:
                     context['query_string'] = self.request.GET['q']

                 search_filter = Q(organisation=self.kwargs['pk']) 

                 items = Compliance.objects.filter(applicant=self.kwargs['pk']).order_by('due_date')

                 context['app_applicants'] = {}
                 context['app_applicants_list'] = []
                 context['app_apptypes'] = list(Application.APP_TYPE_CHOICES)

                 APP_STATUS_CHOICES = []
                 for i in Application.APP_STATE_CHOICES:
                     if i[0] in [1,11,16]:
                         APP_STATUS_CHOICES.append(i)

                 context['app_appstatus'] = list(APP_STATUS_CHOICES)
                 context['compliance'] = items


        return context


#class OrganisationCreate(LoginRequiredMixin, CreateView):
#    """A view to create a new Organisation.
#    """
#    form_class = apps_forms.OrganisationForm
#    template_name = 'accounts/organisation_form.html'
#
#    def get_context_data(self, **kwargs):
#        context = super(OrganisationCreate, self).get_context_data(**kwargs)
#        context['action'] = 'Create'
#        return context
#
#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('organisation_list'))
#        return super(OrganisationCreate, self).post(request, *args, **kwargs)
#
#    def form_valid(self, form):
#        self.obj = form.save()
#        # Assign the creating user as a delegate to the new organisation.
#        Delegate.objects.create(email_user=self.request.user, organisation=self.obj)
#        messages.success(self.request, 'New organisation created successfully!')
#        return HttpResponseRedirect(reverse('organisation_detail', args=(self.obj.pk,)))


#class OrganisationUserCreate(LoginRequiredMixin, CreateView):
#    """A view to create a new Organisation.
#    """
#    form_class = apps_forms.OrganisationForm
#    template_name = 'accounts/organisation_form.html'
#
#    def get_context_data(self, **kwargs):
#        context = super(OrganisationUserCreate, self).get_context_data(**kwargs)
#        context['action'] = 'Create'
#        return context
#
#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(reverse('organisation_list'))
#        return super(OrganisationUserCreate, self).post(request, *args, **kwargs)
#
#    def form_valid(self, form):
#        self.obj = form.save()
#        # Assign the creating user as a delegate to the new organisation.
#        user = EmailUser.objects.get(id=self.kwargs['pk'])
#        Delegate.objects.create(email_user=user, organisation=self.obj)
#        messages.success(self.request, 'New organisation created successfully!')
#        return HttpResponseRedirect(reverse('organisation_detail', args=(self.obj.pk,)))

#class OrganisationDetail(LoginRequiredMixin, DetailView):
#    model = Organisation
#
#    def get_context_data(self, **kwargs):
#        context = super(OrganisationDetail, self).get_context_data(**kwargs)
#        org = self.get_object()
#        context['user_is_delegate'] = Delegate.objects.filter(email_user=self.request.user, organisation=org).exists()
#        return context

class OrganisationUpdate(LoginRequiredMixin, UpdateView):
    """A view to update an Organisation object.
    """
    model = Organisation
    form_class = apps_forms.OrganisationForm

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = self.get_object()

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
            pass 
        else:
           if admin_staff is True:
               return super(OrganisationUpdate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationUpdate, self).get(request, *args, **kwargs)


#    def get(self, request, *args, **kwargs):
#        # Rule: only a delegated user can update an organisation.
#        if not Delegate.objects.filter(email_user=request.user, organisation=self.get_object()).exists():
#            messages.warning(self.request, 'You are not authorised to update this organisation. Please request delegated authority if required.')
#            return HttpResponseRedirect(self.get_success_url())
#        return super(OrganisationUpdate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationUpdate, self).get_context_data(**kwargs)
        context['action'] = 'Update'
        return context

    def get_success_url(self):
        return reverse('organisation_detail', args=(self.get_object().pk,))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        return super(OrganisationUpdate, self).post(request, *args, **kwargs)

class OrganisationContactCreate(LoginRequiredMixin, CreateView):
    """A view to update an Organisation object.
    """
    #model = OrganisationContact
    form_class = apps_forms.OrganisationContactForm
    template_name = 'applications/organisation_contact_form.html'

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        org = Organisation.objects.get(id=self.kwargs['pk'])

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
            pass
        else:
           if admin_staff is True:
               return super(OrganisationContactCreate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationContactCreate, self).get(request, *args, **kwargs)


    def get_context_data(self, **kwargs):
        context = super(OrganisationContactCreate, self).get_context_data(**kwargs)
        context['action'] = 'Create'
#        print self.get_object().pk
#        context['organisation'] = self.get_object().pk 
        return context

    def get_initial(self):
        initial = super(OrganisationContactCreate, self).get_initial()
        initial['organisation'] = self.kwargs['pk']
        # print 'dsf dsaf dsa'
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.kwargs['pk'],'contactdetails')))
        return super(OrganisationContactCreate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.obj = form.save(commit=False)
        org = Organisation.objects.get(id=self.kwargs['pk'])
        self.obj.organisation = org
        self.obj.save()
        # Assign the creating user as a delegate to the new organisation.
        messages.success(self.request, 'Organisation contact created successfully!')
        return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.kwargs['pk'], 'contactdetails')))

class OrganisationContactUpdate(LoginRequiredMixin, UpdateView):
    """A view to update an Organisation object.
    """
    model = OrganisationContact
    form_class = apps_forms.OrganisationContactForm
    template_name = 'applications/organisation_contact_form.html'


    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']
        self.object = self.get_object()

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=self.object.organisation).exists():
            pass
        else:
           if admin_staff is True:
               return super(OrganisationContactUpdate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised.')
               return HttpResponseRedirect(reverse('home_page'))

        return super(OrganisationContactUpdate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(OrganisationContactUpdate, self).get_context_data(**kwargs)
        context['action'] = 'Update'
        return context

    def get_initial(self):
        initial = super(OrganisationContactUpdate, self).get_initial()
        return initial

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.get_object().organisation.id,'contactdetails')))
        return super(OrganisationContactUpdate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        self.obj = form.save()
        # Assign the creating user as a delegate to the new organisation.
        messages.success(self.request, 'Organisation contact updated successfully!')
        return HttpResponseRedirect(reverse('organisation_details_actions', args=(self.get_object().organisation.id, 'contactdetails')))



#class OrganisationAddressCreate(AddressCreate):
#    """A view to create a new address for an Organisation.
#    """
#    def get_context_data(self, **kwargs):
#        context = super(OrganisationAddressCreate, self).get_context_data(**kwargs)
#        org = Organisation.objects.get(pk=self.kwargs['pk'])
#        context['principal'] = org.name
#        return context
#
#    def form_valid(self, form):
#        self.obj = form.save()
#        # Attach the new address to the organisation.
#        org = Organisation.objects.get(pk=self.kwargs['pk'])
#        if self.kwargs['type'] == 'postal':
#            org.postal_address = self.obj
#        elif self.kwargs['type'] == 'billing':
#            org.billing_address = self.obj
#        org.save()
#        return HttpResponseRedirect(reverse('organisation_detail', args=(org.pk,)))


#class RequestDelegateAccess(LoginRequiredMixin, FormView):
#    """A view to allow a user to request to be added to an organisation as a delegate.
#    This view sends an email to all current delegates, any of whom may confirm the request.
#    """
#    form_class = apps_forms.DelegateAccessForm
#    template_name = 'accounts/request_delegate_access.html'
#
#    def get_organisation(self):
#        return Organisation.objects.get(pk=self.kwargs['pk'])
#
#    def get(self, request, *args, **kwargs):
#        # Rule: redirect if the user is already a delegate.
#        org = self.get_organisation()
#        if Delegate.objects.filter(email_user=request.user, organisation=org).exists():
#            messages.warning(self.request, 'You are already a delegate for this organisation!')
#            return HttpResponseRedirect(self.get_success_url())
#        return super(RequestDelegateAccess, self).get(request, *args, **kwargs)
#
#    def get_context_data(self, **kwargs):
#        context = super(RequestDelegateAccess, self).get_context_data(**kwargs)
#        context['organisation'] = self.get_organisation()
#        return context
#
#    def get_success_url(self):
#        return reverse('organisation_detail', args=(self.get_organisation().pk,))
#
#    def post(self, request, *args, **kwargs):
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(self.get_success_url())
#        # For each existing organisation delegate user, send an email that
#        # contains a unique URL to confirm the request. The URL consists of the
#        # requesting user PK (base 64-encoded) plus a unique token for that user.
#        org = self.get_organisation()
#        delegates = Delegate.objects.filter(email_user=request.user, organisation=org)
#        if not delegates.exists():
#            # In the event that an organisation has no delegates, the request
#            # will be sent to all users in the "Processor" group.
#            processor = Group.objects.get(name='Processor')
#            recipients = [i.email for i in EmailUser.objects.filter(groups__in=[processor])]
#        else:
#            recipients = [i.emailuser.email for i in delegates]
#        user = self.request.user
#        uid = urlsafe_base64_encode(force_bytes(user.pk))
#        # Note that the token generator uses the requesting user object to generate a hash.
#        # This means that if the user object changes (e.g. they log out and in again),
#        # the hash will be invalid. Therefore, this request/response needs to occur
#        # fairly promptly to work.
#        token = default_token_generator.make_token(user)
#        url = reverse('confirm_delegate_access', args=(org.pk, uid, token))
#        url = request.build_absolute_uri(url)
#        subject = 'Delegate access request for {}'.format(org.name)
#        message = '''The following user has requested delegate access for {}: {}\n
#        Click here to confirm and grant this access request:\n{}'''.format(org.name, user, url)
#        html_message = '''<p>The following user has requested delegate access for {}: {}</p>
#        <p><a href="{}">Click here</a> to confirm and grant this access request.</p>'''.format(org.name, user, url)
#        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=False, html_message=html_message)
#        # Send a request email to the recipients asynchronously.
#        # NOTE: the lines below should remain commented until (if) async tasking is implemented in prod.
#        #from django_q.tasks import async
#        #async(
#        #    'django.core.mail.send_mail', subject, message,
#        #    settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True, html_message=html_message,
#        #    hook='log_task_result')
#        #messages.success(self.request, 'An email requesting delegate access for {} has been sent to existing delegates.'.format(org.name))
#        # Generate an action record:
#        action = Action(content_object=org, user=user, action='Requested delegate access')
#        action.save()
#        return super(RequestDelegateAccess, self).post(request, *args, **kwargs)


#class ConfirmDelegateAccess(LoginRequiredMixin, FormView):
#    form_class = apps_forms.DelegateAccessForm
#    template_name = 'accounts/confirm_delegate_access.html'
#
#    def get_organisation(self):
#        return Organisation.objects.get(pk=self.kwargs['pk'])
#
#    def get(self, request, *args, **kwargs):
#        # Rule: request user must be an existing delegate.
#        org = self.get_organisation()
#        delegates = Delegate.objects.filter(email_user=request.user, organisation=org)
#        if delegates.exists():
#            uid = urlsafe_base64_decode(self.kwargs['uid'])
#            user = EmailUser.objects.get(pk=uid)
#            token = default_token_generator.check_token(user, self.kwargs['token'])
#            if token:
#                return super(ConfirmDelegateAccess, self).get(request, *args, **kwargs)
#            else:
#                messages.warning(self.request, 'The request delegate token is no longer valid.')
#        else:
#            messages.warning(self.request, 'You are not authorised to confirm this request!')
#        return HttpResponseRedirect(reverse('user_account'))
#
#    def get_context_data(self, **kwargs):
#        context = super(ConfirmDelegateAccess, self).get_context_data(**kwargs)
#        context['organisation'] = self.get_organisation()
#        uid = urlsafe_base64_decode(self.kwargs['uid'])
#        context['requester'] = EmailUser.objects.get(pk=uid)
#        return context
#
#    def get_success_url(self):
#        return reverse('organisation_detail', args=(self.get_organisation().pk,))
#
#    def post(self, request, *args, **kwargs):
#        uid = urlsafe_base64_decode(self.kwargs['uid'])
#        req_user = EmailUser.objects.get(pk=uid)
#        token = default_token_generator.check_token(req_user, self.kwargs['token'])
#        # Change the requesting user state to expire the token.
#        req_user.last_login = req_user.last_login + timedelta(seconds=1)
#        req_user.save()
#        if request.POST.get('cancel'):
#            return HttpResponseRedirect(self.get_success_url())
#        if token:
#            org = self.get_organisation()
#            Delegate.objects.create(email_user=req_user, organisation=org)
#            messages.success(self.request, '{} has been added as a delegate for {}.'.format(req_user, org.name))
#        else:
#            messages.warning(self.request, 'The request delegate token is no longer valid.')
#        return HttpResponseRedirect(self.get_success_url())


class UnlinkDelegate(LoginRequiredMixin, FormView):
    form_class = apps_forms.UnlinkDelegateForm
    template_name = 'accounts/confirm_unlink_delegate.html'

    def get_organisation(self):
        return Organisation.objects.get(pk=self.kwargs['pk'])

    def get(self, request, *args, **kwargs):
        # Rule: request user must be a delegate (or superuser).
        context_processor = template_context(self.request)
        admin_staff = context_processor['admin_staff']

        org = self.get_organisation()
        if Delegate.objects.filter(email_user_id=self.kwargs['user_id'], organisation=org).exists():
           pass 
        else:
           messages.error(self.request, 'User not found')
           return HttpResponseRedirect(self.get_success_url())

        if Delegate.objects.filter(email_user_id=request.user.id, organisation=org).exists():
#        print delegates
#        if request.user.id == delegates.email_user.id:
           donothing = ""
        else:
           if admin_staff is True:
               return super(UnlinkDelegate, self).get(request, *args, **kwargs)
           else:
               messages.error(self.request, 'You are not authorised to unlink a delegated user for {}'.format(org.name))
               return HttpResponseRedirect(self.get_success_url())

        return super(UnlinkDelegate, self).get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(UnlinkDelegate, self).get_context_data(**kwargs)
        context['delegate'] = EmailUser.objects.get(pk=self.kwargs['user_id'])
        return context

    def get_success_url(self):
        return reverse('organisation_details_actions', args=(self.get_organisation().pk,'linkedperson'))

    def post(self, request, *args, **kwargs):
        if request.POST.get('cancel'):
            return HttpResponseRedirect(self.get_success_url())
        return super(UnlinkDelegate, self).post(request, *args, **kwargs)

    def form_valid(self, form):
        # Unlink the specified user from the organisation.
        org = self.get_organisation()
        user = EmailUser.objects.get(pk=self.kwargs['user_id'])
        delegateorguser = Delegate.objects.get(email_user=user, organisation=org)
        delegateorguser.delete()
#        Delegate.objects.delete(email_user=user, organisation=org)
        messages.success(self.request, '{} has been removed as a delegate for {}.'.format(user, org.name))
        # Generate an action record:
        action = Action(content_object=org, user=self.request.user,
            action='Unlinked delegate access for {}'.format(user.get_full_name()))
        action.save()
        return HttpResponseRedirect(self.get_success_url())


def getPDFapplication(request,application_id):

  if request.user.is_superuser:
      app = Application.objects.get(id=application_id)

      filename = 'pdfs/applications/'+str(app.id)+'-application.pdf'
      if os.path.isfile(filename) is False:
#      if app.id:
          pdftool = PDFtool()
          if app.app_type == 4:
              pdftool.generate_emergency_works(app)

      if os.path.isfile(filename) is True:
          pdf_file = open(filename, 'rb')
          pdf_data = pdf_file.read()
          pdf_file.close()
          return HttpResponse(pdf_data, content_type='application/pdf')

