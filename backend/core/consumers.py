from __future__ import annotations

from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication

from .realtime_events import user_group_name


class RealtimeConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = await self.resolve_user()
        if not getattr(user, 'is_authenticated', False):
            await self.close(code=4401)
            return
        self.scope['user'] = user
        self.group_name = user_group_name(int(user.pk))
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        group_name = getattr(self, 'group_name', '')
        if group_name:
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def realtime_event(self, event):
        await self.send_json(event['message'])

    async def resolve_user(self):
        query_string = self.scope.get('query_string', b'').decode('utf-8')
        token = ''
        for part in query_string.split('&'):
            key, _, value = part.partition('=')
            if key == 'token':
                token = value
                break
        if not token:
            return AnonymousUser()
        try:
            auth = JWTAuthentication()
            validated = auth.get_validated_token(token)
            return await database_sync_to_async(auth.get_user)(validated)
        except Exception:
            return AnonymousUser()
