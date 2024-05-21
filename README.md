# Transcript-POC-Server
This project is a Django Backend for AWS Transcribe




# API Doc

## Base URL
```
https://poc-transcript-server.azurewebsites.net/
```
## APIs



`api/register/`: The endpoint to register a new user of this website.
```
method: 'POST',
headers: {
    'Content-Type': 'application/json',
},
body: {
    username:""
    password:""
    email:""
}
```

`api/login/`: The endpoint for user login.
```
method: 'POST',
headers: {
    'Content-Type': 'application/json',
},
body: {
    username:""
    password:""
}
```

`api/upload/`: The endpoint to upload video file to AWS S3.
```
method: 'POST',
body: formData,
headers: {
    'Authorization': `Token ${token}` // Replace with your actual token
}
```

`api/transcribe/`: The endpoint for trascript.
```
method: 'POST',
headers: {
    'Content-Type': 'application/json',
    'Authorization': `Token ${token}`, // Replace with your actual token
},
body: { s3_url: s3Url },
```

`api/transcribe-medical/`: The endpoint for medical trascript.
```
method: 'POST',
headers: {
    'Content-Type': 'application/json',
    'Authorization': `Token ${token}`, // Replace with your actual token
},
body: { s3_url: s3Url },
```

`api/s3-files/`: The endpoint to get the file list of AWS S3
```
method: 'GET',
headers: {
    'Authorization': `Token ${token}`
},
```

`api/summarize/`: The endpoint for transcript summarization.
```
method: 'POST',
headers: {
    'Content-Type': 'application/json',
    'Authorization': `Token ${token}`, // Replace with your actual token
},
body: { text: trans }, // replace the trans with real transcription
```

`api/summarize-file/`: The endpoint to summarize the uploaded files.
```
method: 'POST',
headers: {
    'Authorization': `Token ${token}`, // Replace with your actual token
},
body: formData, // formData is the file data
```