from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class PublicPagesSitemap(Sitemap):
    changefreq = "monthly"

    def items(self):
        return ["home", "about", "sign_up", "login", "privacy", "terms"]

    def location(self, item):
        return reverse(item)
