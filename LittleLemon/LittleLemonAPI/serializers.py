from rest_framework import serializers
from .models import MenuItem, Category, Rating, CartItem, Order, OrderItem
from django.contrib.auth.models import User
from rest_framework.validators import UniqueTogetherValidator
from decimal import Decimal

class CategoryMiniSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='title')

    class Meta:
        model = Category
        fields = ['id', 'name']

class MenuItemSerializer(serializers.ModelSerializer):
    dish = serializers.CharField(source='name')
    stock = serializers.IntegerField(source='inventory', min_value=0)
    price = serializers.DecimalField(max_digits=6, decimal_places=2, coerce_to_string=True, min_value=2)
    category = CategoryMiniSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    price_after_tax = serializers.SerializerMethodField(method_name='get_price_after_tax')
    is_item_of_the_day = serializers.BooleanField(read_only=True)

    class Meta:
        model = MenuItem
        fields = ['id', 'dish', 'price', 'price_after_tax', 'stock', 'category', 'category_id', 'is_item_of_the_day']

    def get_price_after_tax(self, obj):
        tax_rate = Decimal('0.10')  # 10% tax
        return (obj.price + (obj.price * tax_rate)).quantize(Decimal('0.01'))
    
    def validate_dish(self, value: str) -> str:
        # Prevent duplicate names (case-insensitive). Exclude current instance when updating.
        qs = MenuItem.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un plato con ese nombre.')
        return value
        
class SingleItemSerializer(serializers.ModelSerializer):
    dish = serializers.CharField(source='name')
    category = CategoryMiniSerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), source='category', write_only=True)
    stock = serializers.IntegerField(source='inventory', min_value=0)
    price = serializers.DecimalField(max_digits=6, decimal_places=2, coerce_to_string=True, min_value=2)
    is_item_of_the_day = serializers.BooleanField(read_only=True)
    class Meta:
        model = MenuItem
        fields = ['id', 'dish', 'price', 'category', 'category_id', 'stock', 'is_item_of_the_day']
    
    def validate_dish(self, value: str) -> str:
        qs = MenuItem.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un plato con ese nombre.')
        return value

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'slug', 'title']
        read_only_fields = ['id']

class SingleCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'slug', 'title']

class RatingSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all(), default=serializers.CurrentUserDefault())
    
    class Meta:
        model = Rating
        validators = [
            UniqueTogetherValidator(
                queryset=Rating.objects.all(),
                fields=['user', 'menu_item'],
                message="You have already rated this menu item."
            )
        ]
        extra_kwargs = {
            'rating': {
                'max_value': 5,
                'min_value': 0
            }
        }
        fields = ['id', 'menu_item', 'score', 'comment', 'user']


class CartItemSerializer(serializers.ModelSerializer):
    menu_item_id = serializers.PrimaryKeyRelatedField(source='menu_item', queryset=MenuItem.objects.all(), write_only=True)
    dish = serializers.CharField(source='menu_item.name', read_only=True)
    unit_price = serializers.DecimalField(max_digits=6, decimal_places=2, read_only=True)
    total_price = serializers.DecimalField(max_digits=8, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ['id', 'menu_item_id', 'dish', 'quantity', 'unit_price', 'total_price']

    def create(self, validated_data):
        user = self.context['request'].user
        menu_item = validated_data['menu_item']
        quantity = validated_data.get('quantity', 1)
        # Try to get existing cart item
        obj, created = CartItem.objects.get_or_create(user=user, menu_item=menu_item, defaults={
            'quantity': quantity,
            'unit_price': menu_item.price,
        })
        if not created:
            # Update quantity (additive)
            obj.quantity += quantity
            obj.save()
        return obj

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['total_price'] = instance.total_price
        data['unit_price'] = instance.unit_price
        return data


class OrderItemReadSerializer(serializers.ModelSerializer):
    dish = serializers.CharField(source='menu_item.name', read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'dish', 'quantity', 'unit_price', 'total_price']

    def get_total_price(self, obj):
        return obj.total_price


class OrderReadSerializer(serializers.ModelSerializer):
    user = serializers.CharField(source='user.username', read_only=True)
    delivery_crew = serializers.SerializerMethodField()
    items = OrderItemReadSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'user', 'delivery_crew', 'status', 'total', 'date', 'items']

    def get_delivery_crew(self, obj):
        return obj.delivery_crew.username if obj.delivery_crew else None


class ManagerOrderUpdateSerializer(serializers.ModelSerializer):
    delivery_crew = serializers.SlugRelatedField(slug_field='username', queryset=User.objects.all(), allow_null=True, required=False)

    class Meta:
        model = Order
        fields = ['delivery_crew', 'status']


class DeliveryCrewOrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']