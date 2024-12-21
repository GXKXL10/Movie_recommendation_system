from django.urls import path
from recommend import views

urlpatterns = [
     path('', views.index, name='home'),  # Assuming views.home exists and is the landing page
    path('signup/', views.signUp, name='signup'),
    path('login/', views.Login, name='login'),
    path('logout/', views.Logout, name='logout'),
    path('<int:movie_id>/', views.detail, name='detail'),
    path('watch/', views.watch, name='watch'),
    path('recommend/', views.recommend, name='recommend'),
    path('', views.index, name='index'),
]
