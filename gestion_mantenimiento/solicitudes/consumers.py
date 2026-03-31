import json
from channels.generic.websocket import AsyncWebsocketConsumer

class KanbanConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        print("Cliente conectado")

    async def disconnect(self, close_code):
        print("Cliente desconectado")  # Mensaje de desconexión

    async def receive(self, text_data):
        data = json.loads(text_data)
        print("Mensaje recibido:", data)  # Ver el contenido del mensaje
        # Envía de vuelta todo el objeto
        await self.send(text_data=json.dumps(data))  # Enviar el objeto completo de vuelta
