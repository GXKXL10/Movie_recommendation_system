from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, get_object_or_404, redirect
from django.http import Http404, HttpResponseRedirect
from django.db.models import Q, Case, When
from django.contrib import messages
from .models import Movie, Myrating, MyList
from .forms import UserForm
import pandas as pd
from django.shortcuts import render, redirect
from .models import Movie
from .forms import MovieForm
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage
from django.conf import settings


# Helper function to check user authentication and active status
def check_user(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if not request.user.is_active:
        raise Http404
    return None

# Index page (list of movies)
def index(request):
    check_user(request)
    movies = Movie.objects.all()
    query = request.GET.get('q')

    if query:
        movies = Movie.objects.filter(Q(title__icontains=query)).distinct()

    return render(request, 'recommend/list.html', {'movies': movies})

# Movie detail page with options to add to MyList and rate
def detail(request, movie_id):
    check_user(request)
    movie = get_object_or_404(Movie, id=movie_id)

    # Check if the movie is in the user's list
    mylist_entry = MyList.objects.filter(movie_id=movie_id, user=request.user).first()
    update = mylist_entry.watch if mylist_entry else False

    if request.method == "POST":
        if 'watch' in request.POST:
            update = request.POST.get('watch') == 'on'
            MyList.objects.update_or_create(
                movie_id=movie_id, user=request.user, defaults={'watch': update}
            )
            message = "Movie added to your list!" if update else "Movie removed from your list!"
            messages.success(request, message)

        elif 'rating' in request.POST:
            try:
                rate = int(request.POST.get('rating', 0))
                if 1 <= rate <= 5:
                    Myrating.objects.update_or_create(
                        movie_id=movie_id, user=request.user, defaults={'rating': rate}
                    )
                    messages.success(request, "Rating has been submitted!")
                else:
                    messages.error(request, "Invalid rating. Please rate between 1 and 5.")
            except ValueError:
                messages.error(request, "Invalid rating. Please enter a valid number.")

        return redirect('detail', movie_id=movie_id)

    movie_rating = Myrating.objects.filter(user=request.user, movie_id=movie_id).first()
    context = {
        'movie': movie,
        'movie_rating': movie_rating.rating if movie_rating else 0,
        'rate_flag': bool(movie_rating),
        'update': update,
    }
    return render(request, 'recommend/detail.html', context)

# MyList page (movies that user has marked to watch)
def watch(request):
    check_user(request)
    movies = Movie.objects.filter(mylist__watch=True, mylist__user=request.user)
    query = request.GET.get('q')

    if query:
        movies = Movie.objects.filter(Q(title__icontains=query)).distinct()

    return render(request, 'recommend/watch.html', {'movies': movies})

# Recommendation Algorithm Helper Function
def get_similar(movie_name, rating, corrMatrix):
    similar_ratings = corrMatrix[movie_name] * (rating - 2.5)  # Adjust ratings to center around 0
    similar_ratings = similar_ratings.sort_values(ascending=False)
    return similar_ratings

# Recommendation page (movies recommended based on user ratings)
def recommend(request):
    check_user(request)
    
    # Prepare data for recommendations
    movie_rating = pd.DataFrame(list(Myrating.objects.all().values()))
    new_user = movie_rating.user_id.unique().shape[0]
    current_user_id = request.user.id

    # Ensure that a new user has rated at least one movie
    if current_user_id > new_user:
        movie = Movie.objects.get(id=19)  # Replace with a default movie ID
        q = Myrating(user=request.user, movie=movie, rating=0)
        q.save()

    # Create user rating matrix
    userRatings = movie_rating.pivot_table(index=['user_id'], columns=['movie_id'], values='rating')

    # Debugging: Check userRatings shape and sample data
    print(f"User Ratings shape: {userRatings.shape}")
    print(userRatings.head())

    userRatings = userRatings.fillna(0, axis=1)

    # Create the correlation matrix
    corrMatrix = userRatings.corr(method='pearson')

    # Debugging: Check the correlation matrix
    print(f"Correlation Matrix shape: {corrMatrix.shape}")
    print(corrMatrix.head())

    # Get the movies the user has already rated
    user_ratings = pd.DataFrame(list(Myrating.objects.filter(user=request.user).values()))
    movie_id_watched = user_ratings['movie_id'].tolist()

    # Create a dictionary to store recommended movies with their correlation scores
    recommended_movies = {}

    # Loop over each movie the user has rated
    for movie, rating in user_ratings[['movie_id', 'rating']].values:
        # Get the similar movies using the correlation matrix
        similar_movies = corrMatrix[movie] * (rating - 2.5)  # Adjust ratings to center around 0

        # Add similar movies to the recommended_movies dictionary
        for similar_movie, corr_value in similar_movies.items():
            # Only recommend if the movie is not already rated by the user
            if similar_movie not in movie_id_watched and similar_movie not in recommended_movies:
                recommended_movies[similar_movie] = corr_value

    # Sort the recommended movies by their correlation value (descending)
    recommended_movies = dict(sorted(recommended_movies.items(), key=lambda item: item[1], reverse=True))

    # Get top 10 recommended movie IDs
    movies_id_recommend = list(recommended_movies.keys())[:10]

    # If no movies are recommended, fallback to a default movie list
    if not movies_id_recommend:
        movies_id_recommend = [18, 19, 20]  # Fallback movie IDs

    # Debugging: Check the recommended movie IDs
    print(f"Recommended movie IDs: {movies_id_recommend}")

    # Order movies and fetch top 10 movie list
    movie_list = list(Movie.objects.filter(id__in=movies_id_recommend).order_by('-id')[:10])

    # If no movies are recommended, fallback to a default movie list
    if not movie_list:
        movie_list = Movie.objects.filter(id__in=[18, 19, 20])  # Fallback movie IDs

    # Debugging: Log the final list of movies to be displayed
    print(f"Final movie list: {[movie.title for movie in movie_list]}")

    context = {'movie_list': movie_list}
    return render(request, 'recommend/recommend.html', context)

# Sign up page
def signUp(request):
    form = UserForm(request.POST or None)

    if form.is_valid():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        user = authenticate(username=form.cleaned_data['username'], password=form.cleaned_data['password'])

        if user is not None and user.is_active:
            login(request, user)
            return redirect("index")

    return render(request, 'recommend/signUp.html', {'form': form})

# Login page
def Login(request):
    if request.method == "POST":
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(username=username, password=password)

        if user is not None and user.is_active:
            login(request, user)
            return redirect("index")
        else:
            error_message = 'Invalid Login' if user else 'Your account is disabled'
            return render(request, 'recommend/login.html', {'error_message': error_message})

    return render(request, 'recommend/login.html')

# Logout page
def Logout(request):
    logout(request)
    return redirect("login")

# Add movie page
def add_movie(request):
    check_user(request)
    if request.method == "POST":
        movie_name = request.POST.get('movie_name')
        movie_genre = request.POST.get('movie_genre')
        movie_poster = request.FILES.get('movie_poster')

        if not movie_poster:
            # Handle missing poster file
            messages.error(request, "Please upload a movie poster.")
            return redirect('add_movie')
        
        elif not movie_name:
            messages.error(request, "Please enter movie name")
            return redirect('add_movie')
        
        elif not movie_genre:
            messages.error(request, "please enter movie genre")
            return redirect('add_movie')
        

        # Save the movie poster using FileSystemStorage
        fs = FileSystemStorage(location=settings.MEDIA_ROOT)
        poster_name = fs.save(movie_poster.name, movie_poster)

        # Create a new Movie object and save it
        new_movie = Movie(title=movie_name, genre=movie_genre, movie_logo=poster_name)
        new_movie.save()

        messages.success(request, "Movie added successfully!")
        return redirect('home')  # Redirect to the home page after adding the movie

    return render(request, 'recommend/add_movie.html')
