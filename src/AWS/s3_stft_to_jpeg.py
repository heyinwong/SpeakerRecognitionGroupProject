import numpy as np
import boto3
import os
import logging
from botocore.exceptions import ClientError
from PIL import Image


def stft_to_jpeg(spec_mag, label, bucket_name='stft-data', object_name=None):
    # Take a spectrogram and save as jpeg in s3 bucket
    if len(spec_mag.shape) > 2:
        spec_mag_1 = spec_mag[:, :, 0]
    im = Image.fromarray(spec_mag_1)

    if im.mode != 'RGB':
        im = im.convert('RGB')

    file_name = label+'.jpeg'
    im.save(file_name)

    if object_name is None:
        object_name = os.path.basename(file_name)

    # Upload the file
    s3_client = boto3.client('s3')
    try:
        response = s3_client.upload_file(file_name, bucket_name, object_name)
    except ClientError as e:
        logging.error(e)
        success = False
    success = True

    if os.path.exists(file_name):
        os.remove(file_name)
    else:
        print(file_name)

    return success
