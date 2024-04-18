import os
import whisper

from werkzeug.utils import secure_filename
from flask import Flask, request, redirect, Response, render_template_string

app = Flask(__name__)

# HTML form for uploading a file
HTML = '''
<!doctype html>
<title>Upload a File</title>
<h1>Upload a File</h1>
<form method=post enctype=multipart/form-data>
  <input type=file name=file>
  <input type=submit value=Upload>
</form>
'''

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            return redirect(request.url)
        if file:
            # Save the file to a secure location
            filename = secure_filename(file.filename)
            # Ensure the /tmp directory exists
            tmp_dir = '/tmp'
            if not os.path.exists(tmp_dir):
                os.makedirs(tmp_dir)
            filepath = os.path.join(tmp_dir, filename)
            file.save(filepath)
            # Here, we simulate file processing and yield a generator response
            return Response(whisperstt(filepath))

    return render_template_string(HTML)

def whisperstt(filepath):
    model = whisper.load_model(name="large-v3", download_root="/mnt/data", in_memory=True)
    result = model.transcribe(filepath)
    yield result["text"]

if __name__ == '__main__':
    app.run(debug=True)