import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from DataTransformation import LowPassFilter, PrincipalComponentAnalysis
from TemporalAbstraction import NumericalAbstraction
from FrequencyAbstraction import FourierTransformation
from sklearn.cluster import KMeans

# --------------------------------------------------------------
# Load data
# --------------------------------------------------------------
df=pd.read_pickle("../../data/interim/02_outliers_removed_chauvenets.pkl")
predictor_column=list(df.columns[:6])

plt.style.use("fivethirtyeight")
plt.rcParams ["figure.figsize"] = (20, 5)
plt.rcParams ["figure.dpi"] = 100
plt.rcParams ["lines.linewidth"] = 2
# --------------------------------------------------------------
# Dealing with missing values (imputation)
# --------------------------------------------------------------
for col in predictor_column:
    df[col]=df[col].interpolate()
df.info()

# --------------------------------------------------------------
# Calculating set duration
# --------------------------------------------------------------
df[df["set"]==25]["acc_y"].plot()
df[df["set"]==50]["acc_y"].plot()

duration=df[df["set"]==1].index[-1]-df[df["set"]==1].index[0]
duration.seconds

for s in df["set"].unique():
    start=df[df["set"]==s].index[-1]
    stop=df[df["set"]==s].index[0]
    duration=start-stop
    df.loc[(df["set"]==s),"duration"]=duration.seconds

df_duration=df.groupby(["category"])["duration"].mean()

#heavy set contain 5 reps so average duration of each rep in heavy set
df_duration.iloc[0]/5
#medium set contain 10 reps so average duration of each rep in medium set
df_duration.iloc[1]/10 

# --------------------------------------------------------------
# Butterworth lowpass filter
# --------------------------------------------------------------
df_lowpass=df.copy()
Lowpass=LowPassFilter()
#step size =200ms
fs=1000/200     #sampling frequency
cutoff=1.3

df_lowpass=Lowpass.low_pass_filter(df_lowpass,"acc_y",fs,cutoff,order=5)

subset=df_lowpass[df_lowpass["set"]==45]
print(subset["label"][0])

fig, ax =plt.subplots(nrows=2, sharex=True, figsize=(20, 10))
ax[0].plot(subset["acc_y"].reset_index(drop=True), label="raw data")
ax[1].plot(subset["acc_y_lowpass"].reset_index(drop=True), label="butterworth filter")
ax[0].legend (loc="upper center",bbox_to_anchor=(0.5, 1.15),fancybox=True, shadow=True)
ax [1].legend (loc="upper center", bbox_to_anchor=(0.5, 1.15), fancybox=True, shadow=True)

for col in predictor_column:
    df_lowpass=Lowpass.low_pass_filter(df_lowpass,col,fs,cutoff,order=5)
    df_lowpass[col]=df_lowpass[col+"_lowpass"]
    del df_lowpass[col+"_lowpass"]

df_lowpass[df_lowpass["set"]==50]["acc_y"].plot()
# --------------------------------------------------------------
# Principal component analysis PCA
# --------------------------------------------------------------
df_pca=df_lowpass.copy()
PCA= PrincipalComponentAnalysis()

pc_values=PCA.determine_pc_explained_variance(df_pca,predictor_column)

plt. figure(figsize=(10, 10))
plt.plot(range(1,len(predictor_column) + 1), pc_values)
plt.xlabel("principal component number") 
plt.ylabel("explained variance") 
plt.show()

df_pca=PCA.apply_pca(df_pca,predictor_column,3)

subset=df_pca[df_pca["set"]==35]
subset[["pca_1","pca_2","pca_3"]].plot()

# --------------------------------------------------------------
# Sum of squares attributes
# --------------------------------------------------------------
df_squared=df_pca.copy()

acc_r=df_squared["acc_x"]**2+df_squared["acc_y"]**2+df_squared["acc_z"]**2
gyr_r=df_squared["gyr_x"]**2+df_squared["gyr_y"]**2+df_squared["gyr_z"]**2

df_squared["acc_r"]=np.sqrt(acc_r)
df_squared["gyr_r"]=np.sqrt(gyr_r)

subset=df_squared[df_squared["set"]==18]
subset[["acc_r","gyr_r"]].plot(subplots=True)

# --------------------------------------------------------------
# Temporal abstraction
# --------------------------------------------------------------
df_temporal=df_squared.copy()

NumAbs=NumericalAbstraction()

predictor_column=predictor_column+["acc_r","gyr_r"]
#window size
ws=int(1000/200) #as step size=200ms

for col in predictor_column:
    df_temporal=NumAbs.abstract_numerical(df_temporal,[col],ws,"mean")
    df_temporal=NumAbs.abstract_numerical(df_temporal,[col],ws,"std")
    
df_temporal_list=[]
for s in df_temporal["set"].unique():
    subset=df_temporal[df_temporal["set"]==s].copy()
    for col in predictor_column:
        subset=NumAbs.abstract_numerical(subset,[col],ws,"mean")
        subset=NumAbs.abstract_numerical(subset,[col],ws,"std")
    df_temporal_list.append(subset)

df_temporal=pd.concat(df_temporal_list)

subset[["acc_y","acc_y_temp_mean_ws_5","acc_y_temp_std_ws_5"]].plot()
subset[["gyr_y","gyr_y_temp_mean_ws_5","gyr_y_temp_std_ws_5"]].plot()
# --------------------------------------------------------------
# Frequency features
# --------------------------------------------------------------

df_freq=df_temporal.copy().reset_index()
FreqAbs=FourierTransformation()

fs=int(1000/200)
ws=int(2800/200) #average length of repition is 2.8sec

df_freq=FreqAbs.abstract_frequency(df_freq,["acc_y"],ws,fs)
df_freq.columns

subset=df_freq[df_freq["set"]==15]
subset[["acc_y"]].plot()

subset[
        ["acc_y_max_freq",
        "acc_y_freq_weighted",
        "acc_y_pse",
        "acc_y_freq_1.429_Hz_ws_14",
        "acc_y_freq_2.5_Hz_ws_14"]
].plot()

df_freq_list=[]
for s in df_freq["set"].unique():
    print(f"applying fourier transform to set {s}")
    subset = df_freq[df_freq["set"]==s].reset_index(drop=True).copy()
    subset=FreqAbs.abstract_frequency(subset,predictor_column,ws,fs)
    df_freq_list.append(subset)

df_freq=pd.concat(df_freq_list).set_index("epoch (ms)",drop=True)
df_freq.info()
# --------------------------------------------------------------
# Dealing with overlapping windows
# --------------------------------------------------------------
df_freq=df_freq.dropna()

df_freq=df_freq.iloc[::2]
# --------------------------------------------------------------
# Clustering
# --------------------------------------------------------------
df_cluster=df_freq.copy()

cluster_columns=["acc_x","acc_y","acc_z"]
K_values=range(2,10)
inertias=[]

for k in K_values:
    subset=df_cluster[cluster_columns]
    Kmeans=KMeans(n_clusters=k,n_init=20,random_state=0)
    cluster_label=Kmeans.fit_predict(subset)
    inertias.append(Kmeans.inertia_)
    
plt.figure(figsize=(10, 10))
plt.plot(K_values,inertias)
plt.xlabel("k")
plt.ylabel("Sum of squared distances")
plt.show()

subset=df_cluster[cluster_columns]
Kmeans=KMeans(n_clusters=5,n_init=20,random_state=0)
df_cluster["cluster"]=Kmeans.fit_predict(subset)

fig = plt.figure(figsize=(15, 15))
ax = fig.add_subplot(projection="3d")
for c in df_cluster["cluster"].unique():
    subset = df_cluster[df_cluster["cluster"]==c]
    ax.scatter(subset ["acc_x"], subset ["acc_y"], subset ["acc_z"], label=c)
ax.set_xlabel("X-axis")
ax.set_ylabel("Y-axis")
ax.set_zlabel("Z-axis")
plt.legend ()
plt.savefig(f"../../reports/figures/Clusters_labelled.png")
plt.show()

fig = plt.figure(figsize=(15, 15))
ax = fig.add_subplot(projection="3d")
for l in df_cluster["label"].unique():
    subset = df_cluster[df_cluster["label"]==l]
    ax.scatter(subset ["acc_x"], subset ["acc_y"], subset ["acc_z"], label=l)
ax.set_xlabel("X-axis")
ax.set_ylabel("Y-axis")
ax.set_zlabel("Z-axis")
plt.legend ()
plt.savefig(f"../../reports/figures/exercises_labelled.png")
plt.show()

# --------------------------------------------------------------
# Export dataset
# --------------------------------------------------------------
df_cluster.to_pickle("../../data/interim/03_data_features.pkl")