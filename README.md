# 🎞️ Shape Of Movie

Ce projet Python permet d'analyser automatiquement la palette colorimétrique de films. Il extrait des images de chaque vidéo, calcule les couleurs moyennes, structure les données dans des fichiers JSON, puis génère une représentation graphique de la progression des couleurs du film sous forme d'image verticale.

---

## 📌 Fonctionnalités

- 📽️ Extraction automatique d’images depuis des vidéos
- 🎨 Analyse des couleurs moyennes de chaque image
- 🗂️ Structuration des données dans des objets `Film` et `Frame`
- 💾 Export des résultats au format JSON
- 🔁 Traitement récursif des dossiers
- 🖌️ Génération d’une image où chaque ligne représente une frame du film

---

## 🧩 Structure du projet

- `model/film.py` : contient la classe `Film`
- `model/frame.py` : contient la classe `Frame`
- `utils/encoder.py` : encodeur JSON pour les objets `Film`
- `src/collect.py` : regroupe la collecte, l’analyse et l’exportation des données au format json
- `src/exploit.py` : dessine les images à partir des JSON analysés

---

## 🚀 Utilisation

### 1. Préparer les répertoires

- `directoryMoviePath` : dossier contenant les vidéos (`.avi`, `.mp4`, `.mkv`)
- `dataDirectoryPath` : dossier dans lequel seront stockées les images extraites
- `outputPath` : dossier où seront exportés les fichiers `.json` , dossier ou seront les images en sortie

### 2. Lancer le traitement principal

lancer juste le `main.py`
