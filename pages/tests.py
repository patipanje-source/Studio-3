from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomePageTests(TestCase):
    def test_home_redirects_anonymous_visitors_to_login(self):
        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "login/?next=/")

    def test_logged_in_user_sees_homepage(self):
        user = get_user_model().objects.create_user(
            username="homepage-test",
            password="test-password-123",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Every athlete has")
        self.assertContains(response, reverse("all_athletes"))

    def test_athlete_directory_renders(self):
        response = self.client.get(reverse("all_athletes"))

        self.assertEqual(response.status_code, 200)
