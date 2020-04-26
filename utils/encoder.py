from json import JSONEncoder

class FilmEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__