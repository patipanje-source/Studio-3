"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from pages import views 

urlpatterns = [
    # Change 'admin.site.get_admin_urls' to 'admin.site.urls'
    path('admin/', admin.site.urls), 
    
    # Your search paths:
    path('athlete/id/<int:athlete_id>/', views.display_athlete, name='athlete_by_id'),
    path('athlete/name/<str:athlete_name>/', views.display_athlete, name='athlete_by_name'),
]