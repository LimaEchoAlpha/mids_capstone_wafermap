
import s3fs
import zipfile
import tempfile
import numpy as np
from tensorflow import keras
from pathlib import Path
import logging
import os

# Source: https://gist.github.com/ramdesh/f00ec1f5d01f03114264e8f3d0c226e8

AWS_ACCESS_KEY=os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_KEY=os.getenv("AWS_SECRET_ACCESS_KEY")
BUCKET_NAME='wafer-capstone'

def get_s3fs():
  return s3fs.S3FileSystem(key=AWS_ACCESS_KEY, secret=AWS_SECRET_KEY)


def zipdir(path, ziph):
  # Zipfile hook to zip up model folders
  length = len(path) # Doing this to get rid of parent folders
  for root, dirs, files in os.walk(path):
    folder = root[length:] # We don't need parent folders! Why in the world does zipfile zip the whole tree??
    for file in files:
      ziph.write(os.path.join(root, file), os.path.join(folder, file))

            
def s3_save_keras_model(model, model_name):
  with tempfile.TemporaryDirectory() as tempdir:
    model.save(f"{tempdir}/{model_name}")
    # Zip it up first
    zipf = zipfile.ZipFile(f"{tempdir}/{model_name}.zip", "w", zipfile.ZIP_STORED)
    zipdir(f"{tempdir}/{model_name}", zipf)
    zipf.close()
    s3fs = get_s3fs()
    s3fs.put(f"{tempdir}/{model_name}.zip", f"{BUCKET_NAME}/models/{model_name}.zip")
    logging.info(f"Saved zipped model at path s3://{BUCKET_NAME}/models/{model_name}.zip")
 

def s3_get_keras_model(model_name: str) -> keras.Model:
  with tempfile.TemporaryDirectory() as tempdir:
    s3fs = get_s3fs()
    # Fetch and save the zip file to the temporary directory
    s3fs.get(f"{BUCKET_NAME}/models/{model_name}.zip", f"{tempdir}/{model_name}.zip")
    # Extract the model zip file within the temporary directory
    with zipfile.ZipFile(f"{tempdir}/{model_name}.zip") as zip_ref:
        zip_ref.extractall(f"{tempdir}/{model_name}")
    # Load the keras model from the temporary directory
    return keras.models.load_model(f"{tempdir}/{model_name}")


import contextlib
import h5py
from tensorflow.keras.models import load_model

# Source: https://github.com/keras-team/keras/issues/9343#issuecomment-440903847

def s3_get_h5_model(model_obj):

    file_access_property_list = h5py.h5p.create(h5py.h5p.FILE_ACCESS)
    file_access_property_list.set_fapl_core(backing_store=False)
    file_access_property_list.set_file_image(model_obj)  

    file_id_args = {
        'fapl': file_access_property_list,
        'flags': h5py.h5f.ACC_RDONLY,
        'name': b'this should never matter',
    }

    h5_file_args = {
        'backing_store': False,
        'driver': 'core',
        'mode': 'r',
    }

    with contextlib.closing(h5py.h5f.open(**file_id_args)) as file_id:
        with h5py.File(file_id, **h5_file_args) as h5_file:
            loaded_model = load_model(h5_file)
    
    return loaded_model