from typing import Any
from django.contrib.auth import authenticate
from rest_framework import views, status, response, permissions, authtoken
from rest_framework.response import Response
from .serializers import UserSerializer

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import hashlib
import time
import json

from .utils import (
        calculate_tokens, 
        check_token_limit_status, 
        chat_complete, 
        store_txt_file, 
        upload_txt_file_to_openai,
        create_assistant,
        create_thread,
        create_message,
        run_thread,
        retrieve_run,
        delete_assistant,
        delete_txt_file_from_openai,
        delete_thread,
        remove_file,
        get_list_messages,
    )

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


class CreateUserView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return response.Response(serializer.data, status=status.HTTP_201_CREATED)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginView(views.APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        if user:
            token, created = authtoken.models.Token.objects.get_or_create(user=user)
            return response.Response({'token': token.key}, status=status.HTTP_200_OK)
        return response.Response({'error': 'Invalid Credentials'}, status=status.HTTP_400_BAD_REQUEST)

class UploadToS3(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    @csrf_exempt
    def post(self, request):

        if request.method == 'POST':
            file = request.FILES['file']
            s3 = boto3.client('s3',
                            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                            region_name=settings.AWS_S3_REGION_NAME)
            try:
                s3.upload_fileobj(
                    file,
                    settings.AWS_STORAGE_BUCKET_NAME,
                    file.name,
                    ExtraArgs={'ContentType': file.content_type}
                )
                file_url = f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file.name}"
                s3_rul = f"s3://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file.name}"
                return JsonResponse({'file_url': file_url}, status=200)
            except Exception as e:
                return JsonResponse({'error': str(e)}, status=500)
        else:
            return JsonResponse({'error': 'Invalid HTTP method'}, status=400)
        
class TranscribeAudioView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s3_url = request.data.get('s3_url')
        if not s3_url:
            return Response({'error': 'Missing S3 URL'}, status=status.HTTP_400_BAD_REQUEST)

        job_name = self.generate_job_name(s3_url)

        transcribe_client = boto3.client('transcribe', region_name=settings.AWS_S3_REGION_NAME)

        try:
            existing_job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            job_status = existing_job['TranscriptionJob']['TranscriptionJobStatus']
        except transcribe_client.exceptions.BadRequestException:
            existing_job = None
            job_status = None
        
        if job_status == 'COMPLETED':
            return self.handle_existing_job(existing_job)
        elif job_status in ['IN_PROGRESS', 'QUEUED']:
            return self.wait_for_transcription(transcribe_client, job_name)
        elif job_status == 'FAILED':
            return Response({'error': 'Transcription job failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif not existing_job:
            return self.start_new_transcription_job(transcribe_client, s3_url, job_name)

    def generate_job_name(self, s3_url):
        url_hash = hashlib.md5(s3_url.encode('utf-8')).hexdigest()
        return f"TranscriptionJob_{url_hash}"

    def handle_existing_job(self, job):
        transcript_file_uri = job['TranscriptionJob']['Transcript']['TranscriptFileUri']
        sarr = transcript_file_uri.split('/')
        transcript = self.read_s3_json(settings.AWS_STORAGE_BUCKET_NAME_TRANSCRIPTS, sarr[4])
        return Response(transcript, status=status.HTTP_200_OK)

    def wait_for_transcription(self, transcribe_client, job_name):
        while True:
            try:
                job = transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
                job_status = job['TranscriptionJob']['TranscriptionJobStatus']
                if job_status == 'COMPLETED':
                    return self.handle_existing_job(job)
                elif job_status == 'FAILED':
                    return Response({'error': 'Transcription job failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                time.sleep(5)  # Sleep for a while before checking the status again
            except transcribe_client.exceptions.BadRequestException:
                # Handle the case where the job is not found, which should not happen here
                return Response({'error': 'Transcription job not found'}, status=status.HTTP_404_NOT_FOUND)

    def start_new_transcription_job(self, transcribe_client, s3_url, job_name):
        try:
            transcribe_client.start_transcription_job(
                TranscriptionJobName=job_name,
                Media={'MediaFileUri': s3_url},
                MediaFormat='mp4',
                LanguageCode='en-US',
                OutputBucketName=settings.AWS_STORAGE_BUCKET_NAME_TRANSCRIPTS,
            )
            # Wait for the job to complete
            return self.wait_for_transcription(transcribe_client, job_name)
        except (BotoCoreError, ClientError) as error:
            return Response({'error': str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def read_s3_json(self, bucket_name, file_key):
        # Create a client
        s3 = boto3.client('s3')
        # Get the object from the bucket
        obj = s3.get_object(Bucket=bucket_name, Key=file_key)
        # Read the contents of the file
        data = obj['Body'].read().decode('utf-8')
        # Convert string to JSON
        json_data = json.loads(data)
        return json_data

class TranscribeAudioViewMedical(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        s3_url = request.data.get('s3_url')
        if not s3_url:
            return Response({'error': 'Missing S3 URL'}, status=status.HTTP_400_BAD_REQUEST)

        job_name = self.generate_job_name(s3_url)

        transcribe_client = boto3.client('transcribe', region_name=settings.AWS_S3_REGION_NAME)

        try:
            existing_job = transcribe_client.get_medical_transcription_job(MedicalTranscriptionJobName = job_name)
            job_status = existing_job['MedicalTranscriptionJob']['TranscriptionJobStatus']
        except transcribe_client.exceptions.BadRequestException:
            existing_job = None
            job_status = None

        if job_status == 'COMPLETED':
            return self.handle_existing_job(existing_job)
        elif job_status in ['IN_PROGRESS', 'QUEUED']:
            return self.wait_for_transcription(transcribe_client, job_name)
        elif job_status == 'FAILED':
            return Response({'error': 'Transcription job failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        elif not existing_job:
            return self.start_new_transcription_job(transcribe_client, s3_url, job_name)

    def generate_job_name(self, s3_url):
        url_hash = hashlib.md5(s3_url.encode('utf-8')).hexdigest()
        return f"MedicalTranscriptionJob_{url_hash}"

    def handle_existing_job(self, job):
        transcript_file_uri = job['MedicalTranscriptionJob']['Transcript']['TranscriptFileUri']
        sarr = transcript_file_uri.split('/')
        transcript = self.read_s3_json(settings.AWS_STORAGE_BUCKET_NAME_TRANSCRIPTS, sarr[4] + '/' + sarr[5])
        return Response(transcript, status=status.HTTP_200_OK)

    def wait_for_transcription(self, transcribe_client, job_name):
        while True:
            try:
                job = transcribe_client.get_medical_transcription_job(MedicalTranscriptionJobName=job_name)
                job_status = job['MedicalTranscriptionJob']['TranscriptionJobStatus']
                if job_status == 'COMPLETED':
                    return self.handle_existing_job(job)
                elif job_status == 'FAILED':
                    return Response({'error': 'Transcription job failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                time.sleep(5)  # Sleep for a while before checking the status again
            except transcribe_client.exceptions.BadRequestException:
                # Handle the case where the job is not found, which should not happen here
                return Response({'error': 'Transcription job not found'}, status=status.HTTP_404_NOT_FOUND)

    def start_new_transcription_job(self, transcribe_client, s3_url, job_name):
        try:
            transcribe_client.start_medical_transcription_job(
                MedicalTranscriptionJobName=job_name,
                Media={'MediaFileUri': s3_url},
                MediaFormat='mp4',
                LanguageCode='en-US',
                OutputBucketName=settings.AWS_STORAGE_BUCKET_NAME_TRANSCRIPTS,
                Specialty='PRIMARYCARE',
                Type='DICTATION'
            )
            # Wait for the job to complete
            return self.wait_for_transcription(transcribe_client, job_name)
        except (BotoCoreError, ClientError) as error:
            return Response({'error': str(error)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def read_s3_json(self, bucket_name, file_key):
        # Create a client
        s3 = boto3.client('s3')
        # Get the object from the bucket
        obj = s3.get_object(Bucket=bucket_name, Key=file_key)
        # Read the contents of the file
        data = obj['Body'].read().decode('utf-8')
        # Convert string to JSON
        json_data = json.loads(data)
        return json_data

class S3FileListView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]  # Or update as per your permission policy

    def get(self, request):
        s3_client = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME

        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name)
            files = response.get('Contents', [])

            # Format the files as per your requirement
            formatted_files = [
                {
                    'Key': file['Key'],
                    'FileURL': f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com/{file['Key']}",
                    'LastModified': file['LastModified'].strftime('%Y-%m-%d %H:%M:%S'),
                    'Size': file['Size'],
                    'ETag': file['ETag']
                }
                for file in files
            ]

            return Response(formatted_files, status=status.HTTP_200_OK)

        except s3_client.exceptions.NoSuchBucket:
            return Response({'error': 'Bucket does not exist'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class SummarizeTxt(views.APIView):
    permission_classes = [permissions.IsAuthenticated]  # Or update as per your permission policy

    def __init__(self, **kwargs: Any) -> None:
        self.text = ""
        self.max_token = 10000

    def post(self, request):
        self.text = request.data.get('text')
        num_token = calculate_tokens(self.text)
        isTokenLimit = check_token_limit_status(num_token=num_token, max_token=self.max_token)


        if isTokenLimit:
            summary = self.use_chatComplete()    
            print(summary)
        else:
            summary = self.use_assistant()    

        return response.Response({'summary': summary}, status=status.HTTP_200_OK)
    
    def use_assistant(self):
        file_path = store_txt_file(self.text)
        file = upload_txt_file_to_openai(file_path)

        assistant = create_assistant(file_id=file.id)
        thread = create_thread()
        message = create_message(thread_id=thread.id, message="Summarize the lecture content inside the file.")
        run = run_thread(thread_id=thread.id, assistant_id=assistant.id)
        retrieved_run_status = "in_progress"

        while(retrieved_run_status != "completed"):
            retrieved_run = retrieve_run(thread_id=thread.id, run_id=run.id)
            retrieved_run_status = retrieved_run.status
            time.sleep(2)
        
        list_messages = get_list_messages(thread_id=thread.id)

        delete_assistant(assistant_id=assistant.id)
        delete_txt_file_from_openai(file_id=file.id)
        delete_thread(thread_id=thread.id)
        remove_file(file_path=file_path)

        return list_messages.data[0].content[0].text.value

        

    def use_chatComplete(self):
        message = chat_complete(self.text)
        return message.choices[0].message.content

class SummarizeTxtFileUpload(views.APIView):
    permission_classes = [permissions.IsAuthenticated]  # Or update as per your permission policy

    def __init__(self, **kwargs: Any) -> None:
        self.file_path = ""

    def post(self, request):
        file = request.FILES['file']
        # uploaded = store_uploaded_file(file=file)
        if not file:
            return JsonResponse({'error': 'No file provided'}, status=400)

        # Save file to the media directory
        file_name = default_storage.save(f'documents/{file.name}', ContentFile(file.read()))
        self.file_path = default_storage.url(file_name)

        summary = self.use_assistant()

        return response.Response({'summary': summary}, status=status.HTTP_200_OK)

    def use_assistant(self):
        file = upload_txt_file_to_openai(self.file_path)

        assistant = create_assistant(file_id=file.id)
        thread = create_thread()
        message = create_message(thread_id=thread.id, message="Summarize the lecture content inside the file.")
        run = run_thread(thread_id=thread.id, assistant_id=assistant.id)
        retrieved_run_status = "in_progress"

        while(retrieved_run_status != "completed"):
            retrieved_run = retrieve_run(thread_id=thread.id, run_id=run.id)
            retrieved_run_status = retrieved_run.status
            time.sleep(2)
        
        list_messages = get_list_messages(thread_id=thread.id)

        delete_assistant(assistant_id=assistant.id)
        delete_txt_file_from_openai(file_id=file.id)
        delete_thread(thread_id=thread.id)
        remove_file(file_path="." + self.file_path)

        return list_messages.data[0].content[0].text.value
