from flask import Blueprint

record = Blueprint('record', __name__)

from . import views
