from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
import os
import yt_dlp
import assemblyai as aai
from .models import BlogPost
import google.generativeai as genai

# Create your views here.
@login_required
def index(request):
    return render(request, 'index.html')

@csrf_exempt
def generate_blog(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            yt_link = data['link']
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({'error': 'Invalid data sent'}, status=400)

        # get yt title
        try:
            title = yt_title(yt_link)
        except Exception as e:
            print(f"YouTube title error: {str(e)}")
            return JsonResponse({'error': "Failed to fetch video info"}, status=500)

        # get transcript
        try:
            transcription = get_transcription(yt_link)
        except Exception as e:
            print(f"Transcription error: {str(e)}")
            transcription = None
        if not transcription:
            return JsonResponse({'error': " Failed to get transcript"}, status=500)

        # use Gemini to generate the blog
        blog_content = generate_blog_from_transcription(transcription, title)
        if not blog_content:
            return JsonResponse({'error': " Failed to generate blog article"}, status=500)

        # save blog article to database
        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        # return blog article as a response
        return JsonResponse({'content': blog_content})
    else:
        return JsonResponse({'error': 'Invalid request method'}, status=405)

def yt_title(link):
    with yt_dlp.YoutubeDL({'quiet': True, 'noplaylist': True}) as ydl:
        info = ydl.extract_info(link, download=False)
        return info['title']

def download_audio(link):
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(settings.MEDIA_ROOT, '%(id)s.%(ext)s'),
        'quiet': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(link, download=True)
        return ydl.prepare_filename(info)

def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = "YOUR_ASSEMBLYAI_API_KEY"

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text

def generate_blog_from_transcription(transcription,title):
    genai.configure(api_key="YOUR_GEMINI_API_KEY")

    prompt = f"Based on the following transcript from a YouTube video, write a comprehensive blog article, write it based on the transcript, but dont make it look like a youtube video, make it look like a proper blog article. Crucially, adjust the tone of the entire blog article according to the video title: '{title}':\n\n{transcription}\n\nArticle:"
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)

    
        return response.text.strip()
    except Exception as e:
        print(f"Gemini Error: {str(e)}")
        return "Error generating content from Gemini AI."




def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(request, "all-blogs.html", {'blog_articles': blog_articles})

def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(request, 'blog-details.html', {'blog_article_detail': blog_article_detail})
    else:
        return redirect('/')

def user_login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/')
        else:
            error_message = "Invalid username or password"
            return render(request, 'login.html', {'error_message': error_message})

    return render(request, 'login.html')

def user_signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']
        repeatPassword = request.POST['repeatPassword']

        if password == repeatPassword:
            try:
                user = User.objects.create_user(username, email, password)
                user.save()
                login(request, user)
                return redirect('/')
            except:
                error_message = 'Error creating account'
                return render(request, 'signup.html', {'error_message':error_message})
        else:
            error_message = 'Password do not match'
            return render(request, 'signup.html', {'error_message':error_message})

    return render(request, 'signup.html')

def user_logout(request):
    logout(request)
    return redirect('/')