from flask import Flask
from flask_restx import Api
import logging
from dotenv import load_dotenv
from pathlib import Path
import yaml
from ocpp_server.database import Database
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Tüm originlere izin verir,,

load_dotenv()

app = Flask(__name__)
db = Database()

# Swagger setup
with open(Path(__file__).parent / 'docs' / 'swagger.yml') as f:
    swagger_config = yaml.safe_load(f)

api = Api(
    app,
    version='1.0',
    title=swagger_config['info']['title'],
    description=swagger_config['info']['description'],
    doc='/api-docs',
    **swagger_config
)

@app.before_first_request
async def initialize():
    await db.initialize()

# API namespaces
from api.routes.charge_points import api as charge_points_ns
from api.routes.transactions import api as transactions_ns

api.add_namespace(charge_points_ns, path='/api')
api.add_namespace(transactions_ns, path='/api')

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)