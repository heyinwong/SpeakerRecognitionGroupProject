import random

import tensorflow as tf
import librosa
import numpy as np


# Load and pre-process audio file
def load_audio(audio_path, mode='train', win_length=400, sr=16000, hop_length=160, n_fft=512, spec_len=257):
    # Load audio
    wav, sr_ret = librosa.load(audio_path, sr=sr)
    if mode == 'train':
        extended_wav = np.append(wav, wav)
        if np.random.random() < 0.3:
            extended_wav = extended_wav[::-1]
    else:
        extended_wav = np.append(wav, wav[::-1])
    # calculate STFT
    linear = librosa.stft(extended_wav, n_fft=n_fft, win_length=win_length, hop_length=hop_length)
    mag, _ = librosa.magphase(linear)
    freq, freq_time = mag.shape
    assert freq_time >= spec_len, "speaking time should be greater than 1.3s"
    if mode == 'train':
        # random cut
        rand_time = np.random.randint(0, freq_time - spec_len)
        spec_mag = mag[:, rand_time:rand_time + spec_len]
    else:
        spec_mag = mag[:, :spec_len]
    mean = np.mean(spec_mag, 0, keepdims=True)
    std = np.std(spec_mag, 0, keepdims=True)
    spec_mag = (spec_mag - mean) / (std + 1e-5)
    spec_mag = spec_mag[:, :, np.newaxis]
    return spec_mag


# preprocess the  data
def data_generator(data_list_path, spec_len=257):
    with open(data_list_path, 'r') as f:
        lines = f.readlines()
        random.shuffle(lines)
    for line in lines:
        audio_path, label = line.replace('\n', '').split('\t')
        spec_mag = load_audio(audio_path, mode='train', spec_len=spec_len)
        yield spec_mag, np.array(int(label))


# Load training data
def train_reader(data_list_path, batch_size, num_epoch, spec_len=257):
    ds = tf.data.Dataset.from_generator(generator=lambda:data_generator(data_list_path, spec_len=spec_len),
                                        output_types=(tf.float32, tf.int64))

    train_dataset = ds.shuffle(buffer_size=1000) \
        .batch(batch_size=batch_size) \
        .repeat(num_epoch) \
        .prefetch(buffer_size=tf.data.experimental.AUTOTUNE)
    return train_dataset


# Load test data
def test_reader(data_list_path, batch_size, spec_len=257):
    ds = tf.data.Dataset.from_generator(generator=lambda:data_generator(data_list_path, spec_len=spec_len),
                                        output_types=(tf.float32, tf.int64))

    test_dataset = ds.batch(batch_size=batch_size)
    return test_dataset
