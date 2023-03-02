from sklearn.cluster import KMeans
from keras.applications.vgg16 import VGG16
import keras.utils as image
from keras.applications.vgg16 import preprocess_input
import numpy as np
import os
import pickle

# Load pre-trained VGG16 model
model = VGG16(weights='imagenet', include_top=False)

# Directory containing images
image_dir = './skeletons'

# Number of clusters
n_clusters = 5000

# if features.pkl exists, lad it in instead of extracting features
if os.path.exists('features.pkl'):
    with open('features.pkl', 'rb') as f:
        features_dict = pickle.load(f)
else:
    # Extract features from images and create a dictionary of filenames and features
    features_dict = {}
    n = len(os.listdir(image_dir))
    for i, filename in enumerate(os.listdir(image_dir)):
        print(f'processing {i} of {n}')
        if filename.endswith('.png'):
            img_path = os.path.join(image_dir, filename)
            img = image.load_img(img_path, target_size=(224, 224))
            x = image.img_to_array(img)
            x = np.expand_dims(x, axis=0)
            x = preprocess_input(x)
            feature = model.predict(x).flatten()
            features_dict[filename] = feature
    print("pickling the features")
    with open('features.pkl', 'wb') as f:
        pickle.dump(features_dict, f)


print("Perform k-means clustering on extracted features")
kmeans = KMeans(n_clusters=n_clusters, verbose=1)

print(f"fitting {len(features_dict)} features")
kmeans.fit(list(features_dict.values()))

print("pickling the kmeans model")
with open('kmeans.pkl', 'wb') as f:
    pickle.dump(kmeans, f)

print("Get cluster assignments for each image and create a dictionary of filenames and cluster assignments")
cluster_assignments_dict = {}
for i, filename in enumerate(features_dict.keys()):
    cluster_assignments_dict[filename] = kmeans.labels_[i]

print("Save cluster assignments to a pickle file")
with open('cluster_assignments.pkl', 'wb') as f:
    pickle.dump(cluster_assignments_dict, f)
