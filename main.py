
from src.collect import Collect
from src.exploit import Exploit

if __name__ == "__main__":
    
    # Set the directory path
    directoryMoviePath="/home/fyndir/Vidéos/Movies/"
    dataDirectoryPath="data/"
    outputPath="result/"

    Collect(directoryMoviePath,dataDirectoryPath,outputPath)
    Exploit(directoryMoviePath,dataDirectoryPath,outputPath)     

    # Exploit the data