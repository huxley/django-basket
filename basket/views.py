# -*- coding: utf-8 -*-
import datetime
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.conf import settings
from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.contenttypes.models import ContentType
from django.template import loader
from basket.forms import OrderFormset, OrderStatusForm
from basket.utils import render_to, get_order_from_request, create_order_from_request, uid_from_request, send_mail
from basket.models import Status, OrderStatus, Order
from basket.forms import get_order_form

@render_to('basket/basket.html')
def basket(request):
    # do not create order automatically
    order = request.order
    # there are three places where we check that basket is not empty
    # otherwise, return page with empty basket message
    # in order to avoid to show basket with 0 goods
    # 1st place
    if order is None or order.empty():
        return {}

    if request.method == 'POST':
        formset = OrderFormset(request.POST, instance=order)

        # empty basket condition
        # 2nd place
        if len(formset.forms) == 0:
            return {}

        if formset.is_valid():
            formset.save()

            for form in formset.forms:
                if not form.cleaned_data.get('keep', True):
                    # remove items withuot checkboxes
                    form.instance.quantity = 0
                order.set_quantity(form.instance.content_object, form.instance.quantity)
            order.save()

            # 3rd place
            if order.empty():
                return {}

            if not 'refresh' in request.POST: 
                return HttpResponseRedirect(reverse('order_confirm'))
    else:
        formset = OrderFormset(instance=order)

    return {
        'formset': formset,
        'order': order,
    }

@render_to('basket/confirm.html')
def confirm(request):
    # do not create order automatically
    order = request.order

    if order is None or order.empty():
        return HttpResponseRedirect(reverse('basket'))
    
    if request.method == 'POST':
        form = get_order_form()(request.POST, instance=order.orderinfo)
        if form.is_valid():
            orderinfo = form.save(commit=False)
            orderinfo.registered = datetime.datetime.now()
            orderinfo.save()
            first_status = Status.objects.all()[0]
            OrderStatus.objects.create(order=order, type=first_status,
                comment=u'Онлайн заказ')
            message = loader.render_to_string('basket/order.txt', {
                'order': order,
            })
            send_mail(u'Форма заказа', message,
                [manager[1] for manager in settings.MANAGERS])
            return HttpResponseRedirect(reverse('order_thankyou'))
    else:
        form = get_order_form()(instance=order.orderinfo)
    return {'form': form, 'order': order}
    

@render_to('basket/thankyou.html')
def thankyou(request):
    order = Order.objects.get_last(uid_from_request(request))
    return {'order': order}

@render_to('basket/status.html')
def status(request):
    if request.method == 'POST':
        form = OrderStatusForm(request.POST)
        if form.is_valid():
            try:
                order = Order.objects.get(id=form.cleaned_data['order_id'])
                return {
                    'status': order.get_status(),
                    'history': order.orderstatus_set.all(),
                }
            except Order.DoesNotExist:
                return {
                    'form': form,
                    'order_id': form.cleaned_data['order_id']
                }
        else:
            return {'form': form}
    else:
        return {'form': OrderStatusForm()}


# ajax views

@render_to('basket/summary.html')
def add_to_basket(request):
    if request.order is None:
        order = create_order_from_request(request)
    else:
        order = request.order

    content_type_id = request.REQUEST.get('content_type', None)
    object_id = request.REQUEST.get('object_id', None)
    try:
        content_type = ContentType.objects.get(id=content_type_id)
        item = content_type.get_object_for_this_type(id=object_id)
    except ObjectDoesNotExist:
        raise Http404

    order.add_item(item)
    return {'order': order}
