import pyaudio
import wave
import json
import math
import struct
import requests
import asyncio
from ollama import AsyncClient

turn = 0
verification = False

def list_devices():
    p = pyaudio.PyAudio()
    info = p.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')
    for i in range(0, numdevices):
        if (p.get_device_info_by_host_api_device_index(0, i).get('maxInputChannels')) > 0:
            print(f"Input Device id {i} - {p.get_device_info_by_host_api_device_index(0, i).get('name')}")
    p.terminate()

def rms(frame):
    count = len(frame)/2
    format = "%dh" % (count)
    shorts = struct.unpack(format, frame)
    sum_squares = 0.0
    for sample in shorts:
        n = sample * (1.0 / 32768)
        sum_squares += n*n
    return math.sqrt(sum_squares / count)

def record_audio():
    global turn
    turn += 1

    chunk = 1024  # Record in chunks of 1024 samples
    sample_format = pyaudio.paInt16  # 16 bits per sample
    channels = 2  # stereo
    fs = 44100  # Record at 44100 samples per second
    threshold = 0.015  # Audio signal below which is considered silence
    silence_limit = 4  # Silence duration to stop recording (seconds)
    silence_count = int(fs / chunk * silence_limit)  # Convert silence duration to number of chunks

    p = pyaudio.PyAudio()  # Create an interface to PortAudio

    global device_index
    stream = p.open(format=sample_format,
                    channels=channels,
                    rate=fs,
                    frames_per_buffer=chunk,
                    input=True,
                    input_device_index=device_index)

    frames = []  # Initialize array to store frames
    silent_frames = 0  # Count silent consecutive frames

    print("Recording...")

    while True:
        data = stream.read(chunk)
        frames.append(data)
        amplitude = rms(data)
        if amplitude < threshold and len(frames) > 200:
            silent_frames += 1
        else:
            silent_frames = 0

        if silent_frames > silence_count:
            print("Silence detected, stopping recording.")
            break
        else:
            silence_count = 0

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open('input.wav', 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(fs)
    wf.writeframes(b''.join(frames))
    wf.close()

    print("Recording saved to input.wav")

def transcribe_audio(url, audio_file_path):
    """
    Uploads an audio file to the transcription server and prints the transcription response.

    Args:
    url (str): URL of the transcription server.
    audio_file_path (str): Path to the audio file to be transcribed.
    """
    files = {'file': open(audio_file_path, 'rb')}
    try:
        response = requests.post(url, files=files)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        # Print or process the transcription response here
    except requests.exceptions.HTTPError as err:
        print(f"HTTP error occurred: {err}")
    except Exception as err:
        print(f"Other error occurred: {err}")
    finally:
        files['file'].close()
    return response.text

def verify_input():
    verification = str(input("Is this transcription correct? Y/N\n"))
    if verification == "Y" or 'y':
        return True
    else:
        return False
    
async def chat(prompt):
  message = {'role': 'user', 'content': prompt}
  async for part in await AsyncClient().chat(model='llama3', messages=[message], stream=True):
    print(part['message']['content'], end='', flush=True)


while __name__ == '__main__':
    if turn == 0:
        print("\nAvailable devices:")
        list_devices()
        device_index = int(input("Choose a device index: "))

    while verification==False:
        record_audio()
        llm_input = transcribe_audio('http://127.0.0.1:5000', 'input.wav')
        print(llm_input)
        verification = verify_input()

    asyncio.run(chat(llm_input))
