## Speech Recognition to get transcriptions

#### 1. Google Cloud Speech-to-Text (Online)
* Google Cloud Speech-to-Text supports:
    * Sentence-level transcription and confidence
    * Word-level transcription and confidence
    * Speaker-diarization
    * Transcribe inputs from different channels
* To use google cloud speech-to-text function:
    * You should have an authentication for google cloud.
    * You should have google cloud module:`pip install google-cloud-speech`
* You can transcribe 60 minutes of speech per month for free, and then it will cost you a money.
* You can find more information about Google Cloud Speech-to-Text here:
https://cloud.google.com/speech-to-text
* How to get an authentication: https://cloud.google.com/speech-to-text/docs/quickstart-client-libraries

* Usage: `python google_sr.py input_data sampling_rate
    * e.g.,) `python google_sr.py sample.wav 44100`  

#### 2. PocketSphinx (Local Machine)
* You can run PocketSphinx in your local machine. 
* To run `sphinx_sr.py`, you should do:
    * install SpeechRecognition module: `pip install SpeechRecognition` 
    * install SphinxBase and PocketSphinx
        * SphinxBase: https://github.com/cmusphinx/sphinxbase
        * PocketSphinx: https://github.com/cmusphinx/pocketsphinx
        
* Usage: `python sphinx_sr.py input_data`
    * e.g.,) `python sphinx_sr.py sample.wav`