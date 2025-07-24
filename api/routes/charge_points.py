from flask_restx import Namespace, Resource, fields
from ocpp_server.database import Database

api = Namespace('charge_points', description='Charge point operations')

charge_point_model = api.model('ChargePoint', {
    'id': fields.String(required=True),
    'status': fields.String,
    'last_heartbeat': fields.DateTime,
    'config': fields.Raw
})

@api.route('/')
class ChargePointList(Resource):
    @api.marshal_list_with(charge_point_model)
    async def get(self):
        """List all charge points"""
        db = Database()
        return await db.get_charge_points()

@api.route('/<string:charge_point_id>')
@api.param('charge_point_id', 'The charge point identifier')
class ChargePointResource(Resource):
    @api.marshal_with(charge_point_model)
    async def get(self, charge_point_id):
        """Get a specific charge point"""
        db = Database()
        return await db.get_charge_point(charge_point_id)

@api.route('/<string:charge_point_id>/restart')
@api.param('charge_point_id', 'The charge point identifier')
class ChargePointRestart(Resource):
    async def post(self, charge_point_id):
        """Restart a charge point"""
        # Burada OCPP Reset komutu gönderilecek
        return {"status": "Restart command sent"}, 202