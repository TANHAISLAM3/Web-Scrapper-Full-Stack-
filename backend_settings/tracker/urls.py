
from django.urls import path
from .views import review_search

urlpatterns = [
    path('reviews/search/', review_search, name='review_search'),
]