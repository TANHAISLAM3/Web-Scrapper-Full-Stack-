from django.db import models

class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    reviews = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Review(models.Model):
    product = models.ForeignKey(Product, related_name='full_reviews', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    text = models.TextField()
    date = models.CharField(max_length=100)
    rating = models.FloatField(null=True, blank=True)

    is_suspicious = models.BooleanField(default=False)
    sentiment = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.title} ({self.rating}⭐)"

