from django.urls import path
from awstranscribe.views import (
        CreateUserView, 
        LoginView, 
        UploadToS3, 
        TranscribeAudioView, 
        S3FileListView, 
        TranscribeAudioViewMedical,
        SummarizeTxt,
        SummarizeTxtFileUpload
    )

urlpatterns = [
    path('api/register/', CreateUserView.as_view(), name='register'),
    path('api/login/', LoginView.as_view(), name='login'),
    path('api/upload/', UploadToS3.as_view(), name='upload_to_s3'),
    path('api/transcribe/', TranscribeAudioView.as_view(), name='transcribe_audio'),
    path('api/transcribe-medical/', TranscribeAudioViewMedical.as_view(), name='transcribe_audio_medical'),
    path('api/s3-files/', S3FileListView.as_view(), name='s3_file_list'),
    path('api/summarize/', SummarizeTxt.as_view(), name='summarize_text'),
    path('api/summarize-file/', SummarizeTxtFileUpload.as_view(), name='summarize_text'),
]