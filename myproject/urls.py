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
from pages.scoring import medal_calculator

### PATHOMKANT ###
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Existing: search by ID
    path(
        'athlete/id/<int:athlete_id>/',
        views.display_athlete,
        name='athlete_by_id'
    ),

    # Existing: search by name
    path(
        'athlete/name/<str:athlete_name>/',
        views.display_athlete,
        name='athlete_by_name'
    ),

    # NEW: display all athletes
    path(
        'athletes/',
        views.display_all_athletes,
        name='all_athletes'
    ),

    ### PATHOMKANT ###

    # fetchable urls (aka. api endpoints)
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('auth/uid_check/', views.uid_check, name='uid_check'),
    path('manage/events/<int:number>/participants/', views.event_participants, name='event_participants'),
    path('manage/medal-calculator/', medal_calculator, name='medal_calculator'),

    # normal urls (aka. html pages)
    path('', views.home_page_view, name='home'),
    path('manage/', views.admin, name='admin', kwargs={'route': ''}),
    path('manage/<str:route>/', views.admin, name='admin'),
    path('login/', views.auth, name='auth', kwargs={'route': 'login'}),
    path('register/', views.auth, name='auth', kwargs={'route': 'register'}),
    
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
