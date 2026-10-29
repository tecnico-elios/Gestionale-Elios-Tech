"""Isolated regression checks; never connects to the production database."""
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
import httpx
from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from mongomock_motor import AsyncMongoMockClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import inventory_local
from routes.commesse_routes import build_router

class FlowRegression(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncMongoMockClient().test_erp
        inventory_local.set_db(self.db)

    async def test_transfer_response_and_history(self):
        await self.db.products.insert_one(dict(id='p', name='TEST', code='TEST', quantity=10,
            warehouse_id='elios-tech', tipo_gestione='a_quantita'))
        result = await inventory_local.transfer_stock('p', 3, 'elios-tech', 'verona', note='TEST')
        jsonable_encoder(result)  # BSON _id previously raised after successful stock mutation.
        history = await inventory_local.list_transfers()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['id'], result['id'])
        self.assertEqual((await inventory_local.get_item('p'))['quantity'], 7)
        self.assertEqual((await inventory_local.get_item(result['target_product_id'], warehouse_id='verona'))['quantity'], 3)
        with self.assertRaises(RuntimeError):
            await inventory_local.transfer_stock('p', 20, 'elios-tech', 'verona', note='TEST')
        self.assertEqual((await inventory_local.get_item('p'))['quantity'], 7)

    async def test_ship_dispatch_auth_and_retry(self):
        app = FastAPI()
        async def user(): return {'username':'test', 'role':'admin'}
        deps = SimpleNamespace(get_current_user=user, require_password_current=user, require_admin=user)
        app.include_router(build_router(self.db, deps), prefix='/api')
        calls=[]
        @app.post('/api/checklist/send')
        async def send(request: Request):
            calls.append((request.headers.get('authorization'), await request.json()))
            return {'checklist_id':'shipment-test'}
        await self.db.commesse.insert_one({'id':'c','number':'TEST','ordine_cliente_id':'native-order','stato':'bozza_spedizione',
            'righe':[{'product_name':'TEST','qty_richiesta':2,'qty_prelevata':2}],
            'shipment_draft':{'payload':{'items':[]}}})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            response = await client.post('/api/commesse/c/ship', headers={'Authorization':'Bearer test'})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['commessa']['stato'], 'spedita')
            self.assertEqual(calls[0][0], 'Bearer test')
            self.assertTrue(calls[0][1]['shipping_date'])
            self.assertEqual(calls[0][1]['order_page_id'],'native-order')
            again = await client.post('/api/commesse/c/ship')
            self.assertTrue(again.json()['already_shipped'])
            self.assertEqual(len(calls),1)

if __name__ == '__main__': unittest.main()
