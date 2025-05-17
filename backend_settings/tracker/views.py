from django.db.models import Avg, Count, Q, F, Value, IntegerField
from django.db.models.functions import Lower
from .models import Product, Review
from django.shortcuts import render

def review_search(request):
    query = request.GET.get('q', '').lower()
    reviews = Review.objects.all()
    keyword_review_ids = []

    if query:
        keyword_reviews = reviews.filter(
            Q(title__icontains=query) | Q(text__icontains=query)
        )
        reviews = keyword_reviews

        # Count keyword frequency per product manually
        product_keyword_count = {}

        for review in keyword_reviews:
            count = (review.title.lower().count(query) + review.text.lower().count(query))
            if count > 0:
                product_id = review.product_id
                product_keyword_count[product_id] = product_keyword_count.get(product_id, 0) + count

        # Fetch top products based on frequency of keyword mention
        top_products_qs = Product.objects.filter(id__in=product_keyword_count.keys()).annotate(
            keyword_frequency=Value(0, output_field=IntegerField())
        )

        # Replace annotation with actual counts from the dictionary
        top_products = sorted(
            top_products_qs,
            key=lambda p: product_keyword_count.get(p.id, 0),
            reverse=True
        )

        for p in top_products:
            p.keyword_frequency = product_keyword_count.get(p.id, 0)
            p.total_reviews = p.full_reviews.count()
            p.avg_rating = p.full_reviews.aggregate(Avg('rating'))['rating__avg']
    else:
        # Fallback: default top products (by rating)
        top_products = Product.objects.annotate(
            avg_rating=Avg('full_reviews__rating'),
            total_reviews=Count('full_reviews'),
            keyword_frequency=Value(0, output_field=IntegerField())
        ).order_by('-avg_rating')[:5]

    total_reviews = Review.objects.count()
    avg_rating_all = Review.objects.aggregate(avg_rating=Avg('rating'))['avg_rating']

    return render(request, 'review.html', {
        'reviews': reviews,
        'query': query,
        'top_products': top_products[:5],
        'total_reviews': total_reviews,
        'avg_rating_all': avg_rating_all,
    })
