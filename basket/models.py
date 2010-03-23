# -*- coding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django import forms
from datetime import datetime
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes import generic
from basket import settings as basket_settings


class StatusType(models.Model):
    class Meta:
        verbose_name = u'Тип статуса'
        verbose_name_plural = u'Типы статуса'

    name = models.CharField(max_length=20, verbose_name=u'Название')
    closed = models.BooleanField(default=False)


class Status(models.Model):
    class Meta:
        verbose_name = u'Статус заказа'
        verbose_name_plural = u'Статусы заказа'
        ordering = ['date']

    type = models.ForeignKey('StatusType')
    date = models.DateTimeField(default=lambda: datetime.now())
    comment = models.CharField(max_length=100, verbose_name=u'Комментарий',
        blank=True, null=True)


class OrderManager(models.Manager):
    '''
    Custom manager for basket
    methods: 
    
        anonymous(is_anonymous) - returns queryset with all anonymous or authorized users
        get_order(uid) - returns not closed order instance, or creates it
        history(uid) - returns queryset of closed orders
    '''
    def anonymous(self, is_anonymous=True):
        '''
            Returns queryset filtered by anonymous flag.
            returns orders from anonymous users
            Example:
                
                Orders.objects.anonymous()  # get all anonymous orders
                Orders.objects.anonymous(False)  # get all authorized orders
        '''
        if is_anonymous:
            return self.get_query_set().filter(user__isnull=True)
        else:
            return self.get_query_set().filter(session__isnull=True)

    def get_order(self, uid):
        '''
            Get or create order, linked to given user or session.
                uid - User instance or session key (str)
        '''
        if type(uid) is str:
            try:
                session = Session.objects.get(pk=uid)

                try:
                    order = self.get_query_set().get(
                        session=session, status__type__closed=False)
                except Order.DoesNotExist:
                    # create order automatically
                    status_type = StatusType.objects.filter(closed=False)[0]
                    new_status, created = Status.objects.get_or_create(type=status_type)
                    order = Order(session=session, status=new_status)
                    order.save()
                return order

            except Session.DoesNotExist:
                # if session doesnt' exist, order won't be created
                pass

        elif type(uid) is User:
            try:
                order = self.get_query_set().get(
                    user=uid, status__type__closed=False)
            except Order.DoesNotExist:
                # create order automatically
                status_type = StatusType.objects.filter(closed=False)[0]
                new_status, created = Status.objects.get_or_create(type=status_type)
                order = Order(user=uid, status=new_status)
                order.save()

            return order

    def history(self, uid):
        '''
        Returns closed orders of given user or session 
        '''
        if type(uid) is str:
            try:
                session = Session.objects.get(pk=uid)
                history = self.get_query_set().filter(
                    session=session, status__type__closed=True)
                return history
            except Session.DoesNotExist:
                return []
        elif type(uid) is User:
            history = self.get_query_set().filter(
                user=uid, order__status__closed=True)
            return history


class Order(models.Model):
    class Meta:
        verbose_name = u'Заказ'
        verbose_name_plural = u'Заказы'
        ordering = ['status__date', ]

    user = models.ForeignKey(User, null=True, blank=True)
    session = models.ForeignKey(Session, null=True, blank=True)
    status = models.ForeignKey('Status')

    objects = OrderManager()

    def anonymous(self):
        '''
        Returns True is order is from anonymous user
        '''
        if self.user is not None:
            return False
        else:
            return True

    def add_item(self, item):
        item_ct = ContentType.objects.get_for_model(item)
        already_in_order = bool(
            self.items.filter(object_id=item.id, content_type=item_ct).count()
        )

        if already_in_order:
            basket_item = self.items.get(object_id=item.id, content_type=item_ct)
            basket_item.quantity += 1
            basket_item.save()
        else:
            basket_item = BasketItem(content_object=item, quantity=1, order=self)
            basket_item.save()
            self.items.add(basket_item)
            self.save()

    def remove_item(self, item):
        item_ct = ContentType.objects.get_for_model(item)
        self.items.filter(object_id=item.id, content_type=item_ct).delete()

    def set_quantity(self, item, quantity):
        item_ct = ContentType.objects.get_for_model(item)
        already_in_order = bool(
            self.items.filter(object_id=item.id, content_type=item_ct).count()
        )

        if quantity <= 0:
            if already_in_basket:
                self.remove_item(item)
            return

        if already_in_order:
            basket_item = self.items.get(object_id=item.id, content_type=item_ct)
            basket_item.quantity = quantity
            basket_item.save()
        else:
            basket_item = BasketItem(content_object=item, quantity=quantity, basket=self)
            basket_item.save()
            self.items.add(basket_item)
            self.save()

    def flush(self):
        for basket_item in self.items.all():
            basket_item.delete()

    def calculate(self):
        total_goods = 0
        total_price = Decimal('0.0')
        for basket_item in self.items.all():
            try:
                total_price += (basket_item.get_price() * basket_item.quantity)
            except AttributeError:
                pass
            total_goods += basket_item.quantity
        return {'goods': total_goods, 'price': total_price}

    def goods(self):
        return self.calculate()['goods']

    def price(self):
        return self.calculate()['price']

    def empty(self):
        return self.goods() == 0

    def get_uid(self):
        if self.anonymous():
            return self.session
        else:
            return self.user

    def __unicode__(self):
        return 'order #%s' % self.id


class BasketItem(models.Model):
    class Meta:
        ordering = ['object_id']

    order = models.ForeignKey('Order', related_name='items')

    content_type = models.ForeignKey(ContentType)
    object_id = models.PositiveIntegerField()
    content_object = generic.GenericForeignKey('content_type', 'object_id')

    quantity = models.IntegerField(u'Количество')

    def get_price(self):
        return getattr(self.content_object, basket_settings.PRICE_ATTR)
