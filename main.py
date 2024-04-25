import pyaudio
import wave
import math
import struct
import requests
import asyncio
from ollama import AsyncClient
from playsound import playsound

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
    

async def get_llm_response(prompt, queue):
    message = {'role': 'user', 'content': prompt}
    async for part in await AsyncClient().chat('llama3', [message], True):
        await queue.put(part['message']['content'])
    await queue.put(None)


async def text_to_speech(sentence):
    print(f"Sending to text-to-speech: {sentence}")
    #response = requests.post("http://127.0.0.1:7860/run/generate", json={
    #	"data": [
    #		sentence,
    #		"\n",
    #		"None",
    #		"",
    #		"Keanu Reeves",
    #		{"name":"audio.wav","data":"data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="},
    #		0,
    #		1,
    #		1,
    #		2,
    #		40,
    #		0.8,
    #		"P",
    #		8,
    #		0,
    #		0.8,
    #		1,
    #		1,
    #		8,
    #		2,
    #		["Conditioning-Free"],
    #		False,
    #		False,
    #	]
    #}).json()

    #file_loc = (response["data"][0]['name']) + ".wav"
    #print(file_loc)
    #playsound(file_loc)

async def consume_response(queue):
    sentence_parts = []  # Array to store parts of the sentence
    while True:
        response_part = await queue.get()
        if response_part is None:
            if sentence_parts:
                # If there are any remaining parts in the list, process them
                final_sentence = ''.join(sentence_parts)
                await text_to_speech(final_sentence)
            queue.task_done()
            break
        
        # Only proceed if response_part is not empty
        if response_part:
            sentence_parts.append(response_part)  # Add part to the list
            if response_part[-1] in '.?!':  # Check if the last character is a sentence terminator
                complete_sentence = ''.join(sentence_parts)  # Join parts into a complete sentence
                await text_to_speech(complete_sentence)  # Send complete sentence to text-to-speech
                sentence_parts = []  # Reset the parts list for the next sentence

        queue.task_done()


async def main(llm_input):
    queue = asyncio.Queue()
    producer = asyncio.create_task(get_llm_response(llm_input, queue))
    consumer = asyncio.create_task(consume_response(queue))
    await asyncio.gather(producer, consumer)



while __name__ == '__main__':
    verification=False

    if turn == 0:
        print("\nAvailable devices:")
        list_devices()
        device_index = int(input("Choose a device index: "))

    while verification==False:
        record_audio()
        llm_input = transcribe_audio('http://127.0.0.1:5000', 'input.wav')
        print(llm_input)
        verification = verify_input()
        if verification==False:
            break
        else:
            asyncio.run(main(llm_input))

