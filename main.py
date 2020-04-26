# Importing all necessary libraries 
import cv2 
import os 
import time
import glob
from model.film import Film
from model.frame import Frame
import scipy
import scipy.misc
import scipy.cluster
import numpy as np
from PIL import Image
import binascii
import struct
import  json
from utils.encoder import FilmEncoder

# Genere des .jpg à partir du fichier video passer en parametre
def GenFrameImage(path,dataPath):
    movieNameArray=os.path.basename(path).split(".")[:-1]#Remove the extension
    movieName = " ".join(movieNameArray)

    # Read the video from specified path 
    cam = cv2.VideoCapture(path) 
    dataPathName='{}/{}'.format(movieName,dataPath)
    
    try:         
        # creating a folder named data/MovieName
        if not os.path.exists(dataPathName): 
            os.makedirs(dataPathName)
        else :
            print("le film a deja été traité")
            return # Le film a deja été traité 
    
    except OSError: 
        print ('Error: Creating directory of data') 
    
    # frame 
    currentframe = 0
    wishFrame = 0
    fps=GetFrameRate(cam)
    
    while(True): 

        # reading from frame 
        ret,frame = cam.read()
    
        if ret: 
            # if video is still left continue creating images 

            seconde = int(currentframe/fps)
            name = './{}/{}{}'.format(dataPathName,str(seconde),".jpg")

            if (currentframe == wishFrame):
                # writing the extracted images 
                cv2.imwrite(name, frame) 
                wishFrame += fps*3   
                print ('Creating...' + name) 
            
            currentframe += 1 

        else: 
            break
    
    # Release all space and windows once done 
    cam.release() 
    cv2.destroyAllWindows() 

# Recupere tout les path video du dossier en  parametre
def GetAllVideoPath(directoryPath):
    AllVideoPath =[]

    for file in os.listdir(directoryPath):
        path=os.path.join(directoryPath, file)
        if(os.path.isdir(path)):   
            if ("Battlestar Galactica (intégrale de la série de 2004) MULTI 1080p HEVC") in path:
                continue
            if ("Le Bureau des legendes (saisons 1 -2 et 3)") in path:
                continue

            AllVideoPath += GetAllVideoPath(path)              
        else :
            if file.endswith((".avi",".mkv","mp4")) :                
                AllVideoPath.append(path) 

    return AllVideoPath

# Recupere le framerate de la video en parametre
def GetFrameRate(video):
    # Find OpenCV version
    (major_ver, minor_ver, subminor_ver) = (cv2.__version__).split('.')
    
    # With webcam get(CV_CAP_PROP_FPS) does not work.
    # Let's see for ourselves.
    
    if int(major_ver)  < 3 :
        fps = video.get(cv2.cv.CV_CAP_PROP_FPS)      
    else :
        fps = video.get(cv2.CAP_PROP_FPS)   

    return int(fps)

# Recupere la coleur dominante de l'image
def GetPrimalColor(path):
    NUM_CLUSTERS = 5
    
    im = Image.open(path)
    im = im.resize((150, 150))      # optional, to reduce time
    ar = np.asarray(im)
    shape = ar.shape
    ar = ar.reshape(scipy.product(shape[:2]), shape[2]).astype(float)

    print('finding clusters')
    codes, dist = scipy.cluster.vq.kmeans(ar, NUM_CLUSTERS)
    print('cluster centres:\n', codes)

    vecs, dist = scipy.cluster.vq.vq(ar, codes)         # assign codes
    counts, bins = scipy.histogram(vecs, len(codes))    # count occurrences

    index_max = scipy.argmax(counts)                    # find most frequent
    peak = codes[index_max]
    colour = binascii.hexlify(bytearray(int(c) for c in peak)).decode('ascii')
    print('most frequent is %s (#%s)' % (peak, colour))

    return colour

# Recupere Tout les repertoires à partir du path en parametre
def GetAllDirectory(DataDirectoryPath):
    AllMovieDataDir = []
    for file in os.listdir(DataDirectoryPath):
        path=os.path.join(DataDirectoryPath, file)
        if(os.path.isdir(path)): 
            AllMovieDataDir.append(path)
    return AllMovieDataDir

# Cree unFilm avec les données contenu dans le dossiers du path
def getFilmFromDataDir(path):
    movieNameArray=os.path.basename(path).split("/")[-1]#Remove the extension
    movieName = "".join(movieNameArray)
    monFilm = Film(movieName,[])

    for file in os.listdir(path):
        framePath=os.path.join(path, file)
        if(file.endswith((".jpg"))) :    
            monFilm.frames.append(Frame(file,GetPrimalColor(framePath)))                
    return monFilm 

# Export l'object film dans le path au format json
def exportFilmOnJSON(monFilm,resultDirectoryPath):
     # Store data in a JSON file
        output_path = os.path.join(resultDirectoryPath,"{}.json".format(monFilm.titre))
        with open(output_path, "w") as datafile:
            json_data = json.dumps(monFilm, indent=4, cls=FilmEncoder)
            datafile.write(json_data)  

if __name__ == "__main__":
    
    # Set the directory path
    directoryMoviePath="/home/fyndir/Vidéos/Movies/"
    dataDirectoryPath="data/"
    resultDirectoryPath="result/"

    # Collect the picture #
    AllMoviePath = GetAllVideoPath(directoryMoviePath)
    
    # for moviePath in orderedMoviePath :
    #     GenFrameImage(moviePath,dataDirectoryPath)

    # Collect the Data #
    
    AllMovieDataDir = GetAllDirectory(dataDirectoryPath)

    for filmDir in AllMovieDataDir:
        monFilm = getFilmFromDataDir(filmDir)       
        exportFilmOnJSON(monFilm,resultDirectoryPath)      

    # Exploit the data