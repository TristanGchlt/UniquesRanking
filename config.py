from dotenv import load_dotenv
import os
load_dotenv()
PERSISTENT_STORAGE_PATH = '/data/'
class Config : 

    SECRET_KEY = os.getenv('FLASK_SECRET_KEY')

    SQLALCHEMY_DATABASE_URI = f'sqlite:///{PERSISTENT_STORAGE_PATH}data.db'

    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_SUPPORTED_LOCALES = ['en', 'fr', 'es', 'it', 'de']
    BABEL_TRANSLATION_DIRECTORIES = '../translations'
    
    DEBUG = False