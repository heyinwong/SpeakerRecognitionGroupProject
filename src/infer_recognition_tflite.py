import argparse
from email import message
import functools
import os
import shutil
import time
import sys
import shutil

import numpy as np

from tflite_runtime.interpreter import Interpreter

from utils.reader import load_audio
from utils.record import RecordAudio
from utils.utility import add_arguments, print_arguments
from AWS.s3_upload_file import upload_file
from AWS.s3_download_file import download_files

parser = argparse.ArgumentParser(description=__doc__)
add_arg = functools.partial(add_arguments, argparser=parser)
add_arg('audio_db',         str,    'audio_db',               'path to our audio database')
add_arg('input_shape',      str,    '(257, 257, 1)',          'shape of input data')
add_arg('threshold',        float,   0.85,                     'threshold of verification')
add_arg('model_path',       str,    'models/layers_model.tflite',  'path to model')
args = parser.parse_args()

print_arguments(args)

# Load Model
interpreter = Interpreter(args.model_path)
interpreter.allocate_tensors()
print("TFLite Quantized Model Loaded Successfully.")

interpreter.allocate_tensors()
_, height, width, _ = interpreter.get_input_details()[0]['shape']
print("Audio Shape (", width, ",", height, ")")

# obtain average
input_shape = eval(args.input_shape)

person_feature = []
person_name = []

person_feature_cloud = []
person_name_cloud = []

# Cloud metadata
wav_bucket_name = 'armcloud' #'armgroupproject'
#stft_bucket_name = 'stft-data'
#unlabelled_stft_bucket_name = 'unlabelled-stft-data'

# predict the audio
def infer(audio_path, message = True, stft_cloud=False, name=None, mode='infer'):
    time5 = time.time()
    data = load_audio(audio_path, mode=mode, spec_len=input_shape[1], name=name, stft_cloud=stft_cloud)
    time6 = time.time()
    stft_time = np.round(time6-time5, 3)

    time3 = time.time()
    output_details = interpreter.get_output_details()[0]
    input_details = interpreter.get_input_details()[0]

    interpreter.set_tensor(input_details['index'], data[np.newaxis, :])
    interpreter.invoke()

    output = interpreter.get_tensor(output_details['index'])
    time4 = time.time()
    predict_time = np.round(time4-time3, 3)
    if message:
        print('STFT time: {} seconds.'.format(stft_time))
        print("Prediction time = {} seconds.".format(predict_time))
    return output


# Load the database and print out the list of members
def load_audio_db(audio_db_path, message = False, cloud_db = False):
    if not os.path.exists(audio_db_path):
        os.makedirs(audio_db_path)
        
    audios = os.listdir(audio_db_path)
    for audio in audios:
        path = os.path.join(audio_db_path, audio)
        name = audio[:-4]
        feature = infer(path, message = False, mode='load')[0]
        if cloud_db:
            person_name_cloud.append(name)
            person_feature_cloud.append(feature)
        else:  
            person_name.append(name)
            person_feature.append(feature)
        if message:
            print("Loaded %s audio." % name)


# Voicprint recognition
def recognition(path, mode='unlabelled', cloud_db=False):
    name = ''
    pro = 0
    feature = infer(path, mode=mode, stft_cloud=cloud_db)[0]
    if cloud_db:
        for i, person_f in enumerate(person_feature_cloud):
            dist = np.dot(feature, person_f) / (np.linalg.norm(feature) * np.linalg.norm(person_f))
            if dist > pro:
                pro = dist
                name = person_name_cloud[i]
    else:
        for i, person_f in enumerate(person_feature):
            dist = np.dot(feature, person_f) / (np.linalg.norm(feature) * np.linalg.norm(person_f))
            if dist > pro:
                pro = dist
                name = person_name[i]

    return name, pro


# Register new member
def register(path, user_name, cloud_db=False):

    if cloud_db:
        if not os.path.exists('./tmp'):
            os.makedirs('./tmp')
        save_path = os.path.join('./tmp', user_name + os.path.basename(path)[-4:])
        shutil.move(path, save_path)
        message = False
        feature = infer(save_path, message, name=user_name, stft_cloud=cloud_db)[0]
        person_name_cloud.append(user_name)
        person_feature_cloud.append(feature)
        wav_success_upload = upload_file(save_path, wav_bucket_name)
        if wav_success_upload:
             print('\nSuccessfully uploaded audio: {} to the cloud!'.format(user_name+'.wav'))
    else:
        save_path = os.path.join(args.audio_db, user_name + os.path.basename(path)[-4:])
        shutil.move(path, save_path)
        message = False
        feature = infer(save_path, message, name=user_name, stft_cloud=cloud_db)[0]
        person_name.append(user_name)
        person_feature.append(feature)
        print('\nSuccessfully saved audio: {} to the local database!'.format(user_name+'.wav'))


if __name__ == '__main__':
    load_audio_db(args.audio_db, message = True)
    record_audio = RecordAudio()

    print('\n \n \n')
    
    try:
        while True:
            print('\n-------------------------------------------------------------------------------------------------------')
            select_fun = input("Please type in number to choose function:\n type in 0 to register new member,\n type in 1 to do single speaker recognition,\n type in 2 to do continuous speaker recognition, \n type in 3 to exit the program. \n")

            if select_fun == '0':
                print("\nPlease SPEAK SLOWLY for a total of 3 seconds")
                audio_path = record_audio.record()
                name = input("Please type in your name as new member: ")
                if name == '': continue
                while True:
                    cloud_db=input('\nPlease type 1 if you want to store your audio to the cloud, else type 0 to store it in the local database\n')
                    if cloud_db in ['0','1']:
                        break
                    else:
                        print('Invalid input')
                cloud_db = bool(int(cloud_db))
                register(audio_path, name, cloud_db)

            elif select_fun == '1':
                # download 
                while True:
                    cloud_db=input('\nPlease type 1 if you want to access the cloud database, else type 0 to access the local database\n')
                    if cloud_db in ['0','1']:
                        break
                    else:
                        print('Not correct input')
                cloud_db = bool(int(cloud_db))
                
                if cloud_db:
                    time_1 = time.time()
                    print('\nAccessing Cloud Database...')
                    download_files(wav_bucket_name)
                    load_audio_db("tmp", cloud_db=cloud_db)
                    time_2 = time.time()
                    print('Download time = ', np.round(time_2-time_1, 3), ' seconds.')

                # run inference 
                audio_path = record_audio.record(cloud=cloud_db)
                time1 = time.time()
                name, p = recognition(audio_path, mode='unlabelled', cloud_db=cloud_db)
                time2 = time.time()
                if p > args.threshold and "Noise" not in name:
                    print("\nThe one currently speaking is %s with a similarity of %f" % (name.split("_")[0], p))
                    print('Classification time = ', np.round(time2-time1, 3), ' seconds. \n')
                else:
                    print("\nThere's no matched member in the database,try speaking in your natural tone or avoid noisy enviroment \n")

                if not cloud_db:
                    os.remove('audio_db/temp.wav')

            elif select_fun == '2':
                # download 
                while True:
                    cloud_db=input('\nPlease type 1 if you want to access the cloud database, else type 0 to access the local database\n')
                    if cloud_db in ['0','1']:
                        break
                    else:
                        print('Invalid input')
                cloud_db = bool(int(cloud_db))

                if cloud_db:
                    time_1 = time.time()
                    print('\nAccessing Cloud Database...')
                    download_files(wav_bucket_name)
                    load_audio_db("tmp", cloud_db=cloud_db)
                    time_2 = time.time()
                    print('Download time = ', np.round(time_2-time_1, 3), ' seconds.')

                # run inference 
                print("\nRecording has started, press Ctrl+C to quit")
                print("[RECORDER] Listening ...... \n")
                keypress=False
                try:
                    while True:
                        audio_path = record_audio.recordconst(cloud=cloud_db)
                        time1 = time.time()
                        name, p = recognition(audio_path, mode='unlabelled', cloud_db=cloud_db)
                        time2 = time.time()
                        if p > args.threshold and "Noise" not in name:
                            print("The one currently speaking is %s with a similarity of %f" % (name.split("_")[0], p))
                            print('Classification time = ', np.round(time2-time1, 3), ' seconds. \n')
                        else:
                            print("There's no matched member in the database,try speaking in your natural tone or avoid noisy enviroment \n")
                except KeyboardInterrupt:
                    if not cloud_db:
                        os.remove('audio_db/temp.wav')
                    pass

            elif select_fun == '3':
                print('Exiting program...')
                if os.path.exists('./tmp'):
                    shutil.rmtree('./tmp')
                else:
                    pass
                sys.exit()

            else:
                print('\nPlease type either 0, 1, 2 or 3 \n')
                
    except KeyboardInterrupt:
        pass

